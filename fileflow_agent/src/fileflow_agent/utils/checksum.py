import hashlib
from typing import Optional
from fileflow_agent.logging.logger import get_logger

logger = get_logger("fileflow_agent.utils.checksum")

def calculate_checksum(file_path: str, block_size: int = 65536) -> Optional[str]:
    """Calculate SHA-256 checksum of a file."""
    try:
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                hasher.update(block)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating checksum for {file_path}: {e}")
        return None
