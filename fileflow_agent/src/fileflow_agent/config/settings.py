import yaml
import json
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from fileflow_agent.config.models import JobConfigFile

class AppSettings(BaseSettings):
    sftp_host: str = ""
    sftp_user: str = ""
    sftp_password: str = ""
    
    aws_access_key: str = ""
    aws_secret_key: str = ""
    aws_region: str = "us-east-1"
    
    hdfs_host: str = ""
    hdfs_port: int = 9000
    
    log_level: str = "INFO"
    sqlite_db_path: str = "data/tracking.db"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

def load_settings() -> AppSettings:
    return AppSettings()

def load_jobs_config(file_path: str | Path) -> JobConfigFile:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Jobs config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        if path.suffix in [".yaml", ".yml"]:
            data = yaml.safe_load(f)
        elif path.suffix == ".json":
            data = json.load(f)
        else:
            raise ValueError(f"Unsupported config file extension: {path.suffix}")

    # Validate and parse
    return JobConfigFile.model_validate(data)
