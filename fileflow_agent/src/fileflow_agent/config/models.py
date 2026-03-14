from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ConnectorType(str, Enum):
    LOCAL = "local"
    SFTP = "sftp"
    S3 = "s3"
    SCP = "scp"
    HDFS = "hdfs"

class VerificationMethod(str, Enum):
    EXISTS = "file_exists"
    SIZE = "size_match"
    CHECKSUM = "checksum_match"

class SourceConfig(BaseModel):
    type: ConnectorType
    config_ref: Optional[str] = None
    path: str
    file_pattern: Optional[str] = None

class DestinationConfig(BaseModel):
    type: ConnectorType
    config_ref: Optional[str] = None
    path: str
    bucket: Optional[str] = None

class ProcessingConfig(BaseModel):
    enabled: bool = False
    steps: List[str] = Field(default_factory=list)

class BackupConfig(BaseModel):
    enabled: bool = False
    location: Optional[str] = None
    retention_days: Optional[int] = None

class VerificationConfig(BaseModel):
    method: VerificationMethod = VerificationMethod.SIZE

class JobDefinition(BaseModel):
    job_id: str
    enabled: bool = True
    schedule: str
    source: SourceConfig
    destination: DestinationConfig
    processing: Optional[ProcessingConfig] = None
    backup: Optional[BackupConfig] = None
    verification: Optional[VerificationConfig] = None

class JobConfigFile(BaseModel):
    jobs: List[JobDefinition]
