import os
import sys
import uvicorn
import argparse
from fileflow_agent.api.app import set_scheduler
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.config.settings import load_settings, load_jobs_config
from fileflow_agent.tracking.database import init_db
from fileflow_agent.scheduler.scheduler import JobScheduler

logger = get_logger("fileflow_agent.main")


def start_agent(jobs_config_path: str, host: str = "0.0.0.0", port: int = 8000):
    os.environ["FILEFLOW_JOBS_CONFIG"] = jobs_config_path

    settings = load_settings()
    logger.info(f"Starting FileFlow Agent. Log Level: {settings.log_level}")

    init_db()

    try:
        jobs_config = load_jobs_config(jobs_config_path)
    except Exception as e:
        logger.error(f"Failed to load jobs config: {e}")
        sys.exit(1)

    scheduler = JobScheduler(app_config=settings.model_dump())
    scheduler.load_jobs_from_config(jobs_config)
    scheduler.start()
    set_scheduler(scheduler)

    try:
        logger.info(f"Starting API server on {host}:{port}")
        uvicorn.run(
            "fileflow_agent.api.app:app",
            host=host,
            port=port,
            log_level=settings.log_level.lower(),
        )
    except KeyboardInterrupt:
        logger.info("Interrupt received, shutting down gracefully...")
    finally:
        scheduler.shutdown()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FileFlow Agent")
    parser.add_argument(
        "--config", type=str, default="configs/jobs.yaml",
        help="Path to jobs configuration file",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="API host")
    parser.add_argument("--port", type=int, default=8000, help="API port")

    args = parser.parse_args()
    start_agent(args.config, args.host, args.port)
