import os
import sys

# Add src to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from fileflow_agent.tracking.database import init_db
from fileflow_agent.config.models import JobDefinition, SourceConfig, DestinationConfig, ConnectorType, ProcessingConfig, BackupConfig, VerificationConfig, VerificationMethod
from fileflow_agent.services.transfer_service import TransferService

def test_transfer():
    # Setup test db
    os.environ["SQLITE_DB_PATH"] = "data/transfer_test.db"
    init_db()
    
    # Create test directories
    os.makedirs("test_source", exist_ok=True)
    os.makedirs("test_dest", exist_ok=True)
    os.makedirs("test_backup", exist_ok=True)
    
    # Create test file
    with open("test_source/hello.txt", "w") as f:
        f.write("Hello FileFlow Orchestrator!")
        
    # Define a job
    job = JobDefinition(
        job_id="test_local_transfer",
        enabled=True,
        schedule="0 * * * *",
        source=SourceConfig(type=ConnectorType.LOCAL, path="test_source", file_pattern="*.txt"),
        destination=DestinationConfig(type=ConnectorType.LOCAL, path="test_dest"),
        processing=ProcessingConfig(enabled=True, steps=["compress"]),
        backup=BackupConfig(enabled=True, location="test_backup", retention_days=7),
        verification=VerificationConfig(method=VerificationMethod.SIZE)
    )
    
    # Run Orchestrator
    service = TransferService()
    service.execute_job(job)
    
    # Verify outputs
    print("Files in source:", os.listdir("test_source"))
    print("Files in dest:", os.listdir("test_dest"))
    print("Files in backup:", os.listdir(f"test_backup/{job.job_id}"))
    
    # Clean up test db and dirs (uncomment if you want to keep them to inspect)
    # try:
    #     os.remove("data/transfer_test.db")
    # except OSError:
    #     pass

if __name__ == "__main__":
    test_transfer()
