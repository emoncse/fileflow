from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Dict, Any
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.config.models import JobConfigFile, JobDefinition
from fileflow_agent.services.transfer_service import TransferService

logger = get_logger("fileflow_agent.scheduler")

class JobScheduler:
    def __init__(self, app_config: Dict[str, Any] = None):
        self.scheduler = BackgroundScheduler()
        self.transfer_service = TransferService()
        self.app_config = app_config or {}

    def load_jobs_from_config(self, job_config_file: JobConfigFile):
        logger.info("Loading jobs into scheduler")
        for job in job_config_file.jobs:
            if not job.enabled:
                logger.info(f"Skipping disabled job {job.job_id}")
                continue
                
            self.add_job(job)

    def add_job(self, job: JobDefinition):
        try:
            trigger = CronTrigger.from_crontab(job.schedule)
            self.scheduler.add_job(
                func=self.transfer_service.execute_job,
                trigger=trigger,
                args=[job, self.app_config],
                id=job.job_id,
                name=f"Job {job.job_id}",
                replace_existing=True
            )
            logger.info(f"Scheduled job {job.job_id} with cron '{job.schedule}'")
        except Exception as e:
            logger.error(f"Failed to schedule job {job.job_id}: {e}")
    def clear_jobs(self):
        logger.info("Clearing all jobs from scheduler")
        self.scheduler.remove_all_jobs()

    def start(self):
        logger.info("Starting scheduler")
        self.scheduler.start()

    def shutdown(self):
        logger.info("Shutting down scheduler")
        self.scheduler.shutdown()
