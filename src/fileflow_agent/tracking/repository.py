from datetime import datetime
from typing import Optional, List, Dict, Any
from fileflow_agent.tracking.database import get_db_connection
from fileflow_agent.logging.logger import get_logger

logger = get_logger("fileflow_agent.tracking.repository")

class TransferStatus:
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

class VerificationStatus:
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    NOT_REQUIRED = "not_required"

class TrackingRepository:
    def __init__(self):
        pass

    def record_transfer(
        self,
        job_id: str,
        source_type: str,
        source_path: str,
        destination_type: str,
        destination_path: str,
        file_name: str,
        file_size: int,
        checksum: Optional[str] = None,
        transfer_status: str = TransferStatus.PENDING,
    ) -> int:
        """Insert a new transfer record."""
        # Fix: ensure checksum is not mistakenly saving as object, force str or None
        if checksum is not None and not isinstance(checksum, str):
            checksum = str(checksum)

        query = """
        INSERT INTO transfers (
            job_id, source_type, source_path, destination_type, destination_path,
            file_name, file_size, checksum, transfer_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    job_id, source_type, source_path, destination_type, destination_path,
                    file_name, file_size, checksum, transfer_status
                )
            )
            conn.commit()
            return cursor.lastrowid

    def is_duplicate(self, job_id: str, file_name: str, file_size: int, checksum: Optional[str]) -> bool:
        """Check if a file was already successfully transferred for this job."""
        if checksum:
            query = """
            SELECT 1 FROM transfers 
            WHERE job_id = ? AND file_name = ? AND file_size = ? AND checksum = ? 
            AND transfer_status = ? LIMIT 1
            """
            params = (job_id, file_name, file_size, checksum, TransferStatus.SUCCESS)
        else:
            query = """
            SELECT 1 FROM transfers 
            WHERE job_id = ? AND file_name = ? AND file_size = ? 
            AND transfer_status = ? LIMIT 1
            """
            params = (job_id, file_name, file_size, TransferStatus.SUCCESS)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result is not None

    def update_transfer_status(self, transfer_id: int, status: str, failure_reason: Optional[str] = None):
        """Update transfer status and set failure reason if any."""
        query = "UPDATE transfers SET transfer_status = ?, failure_reason = ? WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, failure_reason, transfer_id))
            conn.commit()

    def update_verification_status(self, transfer_id: int, status: str):
        """Update verification status of a transfer."""
        query = "UPDATE transfers SET verification_status = ? WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, transfer_id))
            conn.commit()
            
    def get_recent_transfers(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent transfer operations for the API."""
        query = "SELECT * FROM transfers ORDER BY execution_time DESC LIMIT ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
    def get_stats(self) -> Dict[str, int]:
        """Get summary stats for the API."""
        query = """
        SELECT 
            COUNT(id) as total,
            SUM(CASE WHEN transfer_status = 'success' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN transfer_status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN transfer_status = 'skipped' THEN 1 ELSE 0 END) as skipped
        FROM transfers
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            if not row or row['total'] == 0:
                return {
                    "total_jobs": 0, "successful_transfers": 0, 
                    "failed_transfers": 0, "duplicate_skips": 0
                }
                
            return {
                "total_jobs": row['total'] or 0,
                "successful_transfers": row['successful'] or 0,
                "failed_transfers": row['failed'] or 0,
                "duplicate_skips": row['skipped'] or 0
            }
