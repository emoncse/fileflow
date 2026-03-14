import sqlite3
import os
from pathlib import Path
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.config.settings import load_settings

logger = get_logger("fileflow_agent.tracking.database")

def get_db_connection() -> sqlite3.Connection:
    settings = load_settings()
    db_path = Path(settings.sqlite_db_path)
    
    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(settings.sqlite_db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create the tracking table if it doesn't exist."""
    logger.info("Initializing SQLite database")
    schema = """
    CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_path TEXT NOT NULL,
        destination_type TEXT NOT NULL,
        destination_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        checksum TEXT,
        execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        transfer_status TEXT NOT NULL,
        verification_status TEXT,
        failure_reason TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_transfers_job_id ON transfers(job_id);
    CREATE INDEX IF NOT EXISTS idx_transfers_status ON transfers(transfer_status);
    CREATE INDEX IF NOT EXISTS idx_transfers_fingerprint 
        ON transfers(job_id, file_name, file_size, checksum);
    """
    
    with get_db_connection() as conn:
        conn.executescript(schema)
        conn.commit()
    logger.info("Database schema applied successfully")
