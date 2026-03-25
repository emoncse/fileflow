import os
import shutil
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
            
            logger.info(f"Backing up {file_path} to {backup_path}")
            shutil.copy(file_path, backup_path)
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup {file_path}: {e}")
            return None
