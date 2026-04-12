from datetime import datetime
from typing import Optional, List, Dict, Any
from fileflow_agent.tracking.database import get_db_connection
from fileflow_agent.logging.logger import get_logger

logger = get_logger("fileflow_agent.tracking.repository")

class TransferStatus:
    PENDING    = "pending"
    SUCCESS    = "success"
    FAILED     = "failed"
    SKIPPED    = "skipped"
    UPLOADED   = "uploaded"    # file reached destination; verification pending/failed
    UNVERIFIED = "unverified"  # upload OK, but verification step could not confirm

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

    def is_duplicate(self, job_id: str, file_name: str, file_size: int, checksum) -> bool:
        """
        Check if this file has already been sent for this job.

        We treat SUCCESS, UPLOADED, and UNVERIFIED all as "already sent" so that a
        file which was physically transferred but whose verification failed does NOT
        get re-uploaded on the next scheduler run.
        """
        SENT_STATUSES = (
            TransferStatus.SUCCESS,
            TransferStatus.UPLOADED,
            TransferStatus.UNVERIFIED,
        )
        placeholders = ",".join("?" * len(SENT_STATUSES))

        if checksum:
            query = f"""
            SELECT 1 FROM transfers
            WHERE job_id = ? AND file_name = ? AND file_size = ? AND checksum = ?
              AND transfer_status IN ({placeholders})
            LIMIT 1
            """
            params = (job_id, file_name, file_size, checksum, *SENT_STATUSES)
        else:
            query = f"""
            SELECT 1 FROM transfers
            WHERE job_id = ? AND file_name = ? AND file_size = ?
              AND transfer_status IN ({placeholders})
            LIMIT 1
            """
            params = (job_id, file_name, file_size, *SENT_STATUSES)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone() is not None

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

    def update_destination_path(self, transfer_id: int, destination_path: str):
        """Update the resolved destination path after upload completes."""
        query = "UPDATE transfers SET destination_path = ? WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (destination_path, transfer_id))
            conn.commit()
            
    def get_recent_transfers(
        self,
        limit: int = 20,
        offset: int = 0,
        job_id: str = None,
        file_name: str = None,
        status: str = None,
        date_from: str = None,
        date_to: str = None,
        source_type: str = None,
        dest_type: str = None,
    ) -> dict:
        """Filterable, paginated query. Returns {transfers, total, page, page_size, pages}."""
        conditions: list[str] = []
        params: list = []

        if job_id:
            conditions.append("job_id LIKE ?")
            params.append(f"%{job_id}%")
        if file_name:
            conditions.append("file_name LIKE ?")
            params.append(f"%{file_name}%")
        if status:
            conditions.append("transfer_status = ?")
            params.append(status)
        if date_from:
            conditions.append("execution_time >= ?")
            params.append(f"{date_from} 00:00:00")
        if date_to:
            conditions.append("execution_time <= ?")
            params.append(f"{date_to} 23:59:59")
        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)
        if dest_type:
            conditions.append("destination_type = ?")
            params.append(dest_type)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        count_query = f"SELECT COUNT(*) AS total FROM transfers {where}"
        data_query  = f"SELECT * FROM transfers {where} ORDER BY execution_time DESC LIMIT ? OFFSET ?"

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(count_query, params)
            total: int = cursor.fetchone()["total"]

            cursor.execute(data_query, [*params, limit, offset])
            rows = cursor.fetchall()

        page = (offset // limit) + 1
        pages = max(1, (total + limit - 1) // limit)

        return {
            "transfers": [dict(r) for r in rows],
            "total":     total,
            "page":      page,
            "page_size": limit,
            "pages":     pages,
        }
            
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
