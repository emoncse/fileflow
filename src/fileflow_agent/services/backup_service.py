import os
import shutil
import time
from typing import Optional
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.config.models import BackupConfig

logger = get_logger("fileflow_agent.services.backup_service")

class BackupService:
    def __init__(self):
        pass

    def perform_backup(self, file_path: str, job_id: str, config: Optional[BackupConfig]) -> Optional[str]:
        if not config or not config.enabled:
            return None
            
        if not config.location:
            logger.warning("Backup enabled but no location provided. Skipping.")
            return None
            
        try:
            backup_dir = os.path.join(config.location, job_id)
            os.makedirs(backup_dir, exist_ok=True)
            
            filename = os.path.basename(file_path)
            backup_path = os.path.join(backup_dir, filename)
            
            logger.info(f"Moving {file_path} to backup location {backup_path}")
            
            try:
                # Use shutil.copy as copy_function to avoid copying stat (ownership) 
                # which causes EPERM on many NFS/CIFS mounts.
                shutil.move(file_path, backup_path, copy_function=shutil.copy)
            except Exception as move_e:
                logger.warning(f"Standard move failed ({move_e}), falling back to copyfile + remove.")
                shutil.copyfile(file_path, backup_path)
                os.remove(file_path)

            # Stamp the backup file's mtime to now so that retention policy
            # calculates age from the time of backup, not the original file timestamp.
            try:
                now = time.time()
                os.utime(backup_path, (now, now))
                logger.info(f"Backup complete. Retention clock starts now for {backup_path}")
            except Exception as utime_e:
                logger.warning(f"Backup succeeded, but could not update timestamp for {backup_path}: {utime_e}")
                
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup {file_path}: {e}")
            return None
