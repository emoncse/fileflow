import os
import sys

# Add src to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from fileflow_agent.tracking.database import init_db
from fileflow_agent.tracking.repository import TrackingRepository, TransferStatus

def test_tracking():
    # Setup test db
    os.environ["SQLITE_DB_PATH"] = "data/test_tracking.db"
    
    # Initialize schema
    init_db()
    
    repo = TrackingRepository()
    
    # Test record_transfer
    transfer_id = repo.record_transfer(
        job_id="test_job",
        source_type="local",
        source_path="/tmp/test.txt",
        destination_type="s3",
        destination_path="s3://bucket/test.txt",
        file_name="test.txt",
        file_size=1024,
        checksum="abcdef123456",
        transfer_status=TransferStatus.PENDING
    )
    print(f"Recorded transfer with ID: {transfer_id}")
    
    # Test update status
    repo.update_transfer_status(transfer_id, TransferStatus.SUCCESS)
    print("Updated transfer status to SUCCESS")
    
    # Test is_duplicate
    is_dupe = repo.is_duplicate(
        job_id="test_job",
        file_name="test.txt",
        file_size=1024,
        checksum="abcdef123456"
    )
    print(f"Is duplicate? {is_dupe}")  # Expected True
    
    # Test stats
    stats = repo.get_stats()
    print(f"Stats: {stats}") # Expected 1 success
    
    # Clean up test db
    try:
        os.remove("data/test_tracking.db")
    except OSError:
        pass

if __name__ == "__main__":
    test_tracking()
