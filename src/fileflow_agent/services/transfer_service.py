import os
import tempfile
from typing import Dict, Any
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.config.models import JobDefinition, ConnectorType
from fileflow_agent.connectors.factory import ConnectorFactory
from fileflow_agent.processing.pipeline import ProcessingPipeline
from fileflow_agent.tracking.repository import TrackingRepository, TransferStatus, VerificationStatus
from fileflow_agent.services.verification_service import VerificationService
from fileflow_agent.services.backup_service import BackupService
from fileflow_agent.services.retention_service import RetentionService
from fileflow_agent.utils.checksum import calculate_checksum

logger = get_logger("fileflow_agent.services.transfer_service")

class TransferService:
    def __init__(self):
        self.repo = TrackingRepository()
        self.processing = ProcessingPipeline()
        self.verification = VerificationService()
        self.backup = BackupService()
        self.retention = RetentionService()

    def execute_job(self, job: JobDefinition, app_config: Dict[str, Any] = None):
        """Executes a single job from start to finish."""
        logger.info(f"Starting execution for job: {job.job_id}")
        app_config = app_config or {}

        try:
            # Merge per-job connection details into the config so connectors
            # (e.g. SFTP) can read host/port/username from self.config['connection'].
            source_config = {**app_config, 'connection': (job.source.connection or {})}
            dest_config = {**app_config, 'connection': (job.destination.connection or {})}

            source = ConnectorFactory.get_source_connector(job.source.type, source_config)
            dest = ConnectorFactory.get_destination_connector(job.destination.type, dest_config)
            
            files = source.list_files(job.source.path, job.source.file_pattern)
            
            if not files:
                logger.info(f"No files found for job: {job.job_id}")
                return
                
            for file_info in files:
                self._process_single_file(job, file_info, source, dest)
                
        except Exception as e:
            logger.error(f"Job execution failed for {job.job_id}: {e}")

    def _process_single_file(self, 
                             job: JobDefinition, 
                             file_info: Dict[str, Any], 
                             source, 
                             dest):
        
        file_name = file_info["file_name"]
        file_size = file_info["file_size"]
        remote_source_path = file_info["path"]
        
        logger.info(f"Processing file: {file_name}")
        
        # Pre-compute the expected destination path (based on original filename, before processing).
        # Used for SKIPPED records where we never reach upload, and as the initial value for PENDING.
        expected_dest_path = f"{job.destination.path.rstrip('/')}/{file_name}"
        if job.destination.bucket:
            expected_dest_path = f"s3://{job.destination.bucket}/{expected_dest_path.lstrip('/')}"

        # Check database for duplicate BEFORE doing heavy work (checksum might be None here)
        if self.repo.is_duplicate(job.job_id, file_name, file_size, None):
            logger.info(f"File {file_name} skipped as duplicate (size match)")
            self.repo.record_transfer(
                job.job_id, job.source.type.value, remote_source_path,
                job.destination.type.value, expected_dest_path,
                file_name, file_size, None, TransferStatus.SKIPPED
            )
            return

        with tempfile.TemporaryDirectory() as temp_dir:
            local_download_path = os.path.join(temp_dir, file_name)
            
            # 1. Download File
            try:
                source.download_file(remote_source_path, local_download_path)
            except Exception as e:
                logger.error(f"Failed to download {file_name}: {e}")
                return

            # Calculate Checksum
            checksum = calculate_checksum(local_download_path)
            
            # Check duplicate again (with checksum)
            if self.repo.is_duplicate(job.job_id, file_name, file_size, checksum):
                logger.info(f"File {file_name} skipped as duplicate (checksum match)")
                self.repo.record_transfer(
                    job.job_id, job.source.type.value, remote_source_path,
                    job.destination.type.value, expected_dest_path,
                    file_name, file_size, checksum, TransferStatus.SKIPPED
                )
                return

            # 2. Record Pending Transfer (dest path uses original filename as placeholder;
            #    it will be updated to the real resolved path after upload in step 4).
            transfer_id = self.repo.record_transfer(
                job.job_id, job.source.type.value, remote_source_path,
                job.destination.type.value, expected_dest_path,
                file_name, file_size, checksum, TransferStatus.PENDING
            )

            # 3. Processing Pipeline
            current_local_path = local_download_path
            out_file_name = file_name
            if job.processing and job.processing.enabled:
                try:
                    current_local_path = self.processing.execute_pipeline(
                        job.processing.steps, current_local_path, {"rename_prefix": f"{job.job_id}_"}
                    )
                    out_file_name = os.path.basename(current_local_path)
                except Exception as e:
                    logger.error(f"Processing failed for {file_name}: {e}")
                    self.repo.update_transfer_status(transfer_id, TransferStatus.FAILED, str(e))
                    return

            # 4. Upload File
            try:
                # Resolve final dest path (out_file_name may differ from file_name if processing renamed it)
                remote_dest_path = f"{job.destination.path.rstrip('/')}/{out_file_name}"
                if job.destination.bucket:
                    remote_dest_path = f"s3://{job.destination.bucket}/{remote_dest_path.lstrip('/')}"

                dest.upload_file(current_local_path, remote_dest_path)
                # Update the record with the real resolved destination path.
                self.repo.update_destination_path(transfer_id, remote_dest_path)
                # Mark as UPLOADED immediately — file is physically on destination.
                # This prevents re-upload if verification fails (UNVERIFIED != FAILED).
                self.repo.update_transfer_status(transfer_id, TransferStatus.UPLOADED)
            except Exception as e:
                logger.error(f"Upload failed for {file_name}: {e}")
                self.repo.update_transfer_status(transfer_id, TransferStatus.FAILED, str(e))
                return

            # 5. Verification
            try:
                is_verified = self.verification.verify(
                    remote_dest_path, current_local_path, dest, job.verification
                )
                if not is_verified:
                    raise ValueError("Verification step returned False")
                self.repo.update_verification_status(transfer_id, VerificationStatus.SUCCESS)
            except Exception as e:
                logger.warning(
                    f"Verification could not confirm {file_name} on destination: {e}. "
                    f"File was physically uploaded (status=UNVERIFIED) — will NOT re-upload."
                )
                # UNVERIFIED = uploaded but not confirmed. is_duplicate() treats this as sent.
                self.repo.update_transfer_status(
                    transfer_id, TransferStatus.UNVERIFIED, f"Verification failed: {e}"
                )
                self.repo.update_verification_status(transfer_id, VerificationStatus.FAILED)
                # Still proceed to backup — the file was transferred.

            # 6. Mark Success
            self.repo.update_transfer_status(transfer_id, TransferStatus.SUCCESS)

            # 7. Backup and Retention
            # For LOCAL sources: move the original source file to backup (archives it out of source dir).
            # For remote sources (SFTP, S3, etc.): move the temp downloaded copy to backup
            # (the remote original stays on the server; a separate delete step would be needed to remove it).
            if job.backup and job.backup.enabled:
                try:
                    if job.source.type == ConnectorType.LOCAL:
                        backup_file_path = remote_source_path   # original file on disk → gets moved out of source
                    else:
                        backup_file_path = local_download_path  # temp pre-processing copy for remote sources
                    self.backup.perform_backup(backup_file_path, job.job_id, job.backup)
                    self.retention.apply_retention(job.job_id, job.backup)
                except Exception as e:
                    logger.error(f"Backup/Retention failed for {file_name}: {e}")
