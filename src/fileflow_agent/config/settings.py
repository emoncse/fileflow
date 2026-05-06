import os
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
    # Empty defaults so the S3 connector falls through to boto3's native resolution
    # chain (AWS_REGION / AWS_DEFAULT_REGION env, then ~/.aws/config) when neither
    # the per-job connection nor the .env explicitly specifies a region.
    aws_region: str = ""
    
    hdfs_host: str = ""
    hdfs_port: int = 9000
    
    log_level: str = "INFO"
    
    # Internal variables pointing to workspace relatives
    _workspace: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def workspace(self) -> str:
        return os.environ.get("FILEFLOW_WORKSPACE", os.getcwd())

    @property
    def sqlite_db_path(self) -> str:
        return os.path.join(self.workspace, "data", "tracking.db")

def load_settings() -> AppSettings:
    ws = os.environ.get("FILEFLOW_WORKSPACE", os.getcwd())
    env_path = os.path.join(ws, ".env")
    return AppSettings(_env_file=env_path)

def load_jobs_config(file_path: str | Path = None) -> JobConfigFile:
    if file_path is None:
        ws = os.environ.get("FILEFLOW_WORKSPACE", os.getcwd())
        file_path = os.path.join(ws, "configs", "jobs.yaml")
        
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

    return JobConfigFile.model_validate(data)
