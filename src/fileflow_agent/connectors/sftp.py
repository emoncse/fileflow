from typing import List, Dict, Any, Optional
from fileflow_agent.connectors.base import SourceConnector, DestinationConnector

from fileflow_agent.logging.logger import get_logger

logger = get_logger("fileflow_agent.connectors.sftp")

class SFTPSourceConnector(SourceConnector):
    def list_files(self, path: str, pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.config.get('connection', {})
        host = conn.get('host', 'unknown_host')
        logger.info(f"Listing files on SFTP server: {host} at {path}")
        return []
    def download_file(self, remote_path: str, local_path: str) -> None:
        pass
    def get_metadata(self, remote_path: str) -> Dict[str, Any]:
        return {}

class SFTPDestinationConnector(DestinationConnector):
    def upload_file(self, local_path: str, remote_path: str) -> None:
        conn = self.config.get('connection', {})
        host = conn.get('host', 'unknown_host')
        logger.info(f"Uploading file to SFTP server: {host} at {remote_path}")
        pass
    def create_directories(self, path: str) -> None:
        pass
    def verify_file(self, remote_path: str, expected_size: int, expected_checksum: Optional[str] = None) -> bool:
        return True
