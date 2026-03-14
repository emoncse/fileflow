import os
import time
from typing import Optional
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.config.models import BackupConfig

logger = get_logger("fileflow_agent.services.retention_service")

class RetentionService:
    def __init__(self):
        pass

    def apply_retention(self, job_id: str, config: Optional[BackupConfig]):
        if not config or not config.enabled or not config.location or not config.retention_days:
            return

        backup_dir = os.path.join(config.location, job_id)
        if not os.path.exists(backup_dir):
            return

        logger.info(f"Applying retention policy for job {job_id} in {backup_dir} (keep {config.retention_days} days)")
        
        current_time = time.time()
        max_age_seconds = config.retention_days * 86400

        try:
            for file_name in os.listdir(backup_dir):
                file_path = os.path.join(backup_dir, file_name)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        logger.info(f"Retention policy: deleting old backup {file_path}")
                        os.remove(file_path)
        except Exception as e:
            logger.error(f"Error applying retention policy: {e}")
