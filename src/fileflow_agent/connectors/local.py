import os
import shutil
from fileflow_agent.utils.pattern import match_pattern
from typing import List, Dict, Any, Optional
from fileflow_agent.connectors.base import SourceConnector, DestinationConnector
from fileflow_agent.logging.logger import get_logger

logger = get_logger("fileflow_agent.connectors.local")

class LocalSourceConnector(SourceConnector):
    def list_files(self, path: str, pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        logger.debug(f"Listing files in local path: {path} with pattern: {pattern}")
        files = []
        if not os.path.exists(path) or not os.path.isdir(path):
            logger.warning(f"Source path {path} does not exist or is not a directory")
            return files
            
        for file_name in os.listdir(path):
            if not match_pattern(file_name, pattern):
                continue
            
            full_path = os.path.join(path, file_name)
            if os.path.isfile(full_path):
                files.append({
                    "file_name": file_name,
                    "file_size": os.path.getsize(full_path),
                    "path": full_path
                })
        return files

    def download_file(self, remote_path: str, local_path: str) -> None:
        logger.debug(f"Copying local file {remote_path} to {local_path}")
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        shutil.copy2(remote_path, local_path)

    def get_metadata(self, remote_path: str) -> Dict[str, Any]:
        if not os.path.exists(remote_path):
            raise FileNotFoundError(f"File {remote_path} not found")
            
        stat = os.stat(remote_path)
        return {
            "size": stat.st_size,
            "mtime": stat.st_mtime
        }

class LocalDestinationConnector(DestinationConnector):
    def upload_file(self, local_path: str, remote_path: str) -> None:
        logger.debug(f"Copying file {local_path} to {remote_path}")
        self.create_directories(os.path.dirname(remote_path))
        shutil.copy2(local_path, remote_path)

    def create_directories(self, path: str) -> None:
        if path:
            os.makedirs(path, exist_ok=True)

    def verify_file(self, remote_path: str, expected_size: int, expected_checksum: Optional[str] = None) -> bool:
        if not os.path.exists(remote_path):
            logger.error(f"Verification failed: {remote_path} does not exist")
            return False
            
        actual_size = os.path.getsize(remote_path)
        if actual_size != expected_size:
            logger.error(f"Verification failed for {remote_path}: expected size {expected_size}, got {actual_size}")
            return False
            
        # Checksum validation is optional and usually done by the orchestrator
        return True
