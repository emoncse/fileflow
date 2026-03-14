from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class SourceConnector(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def list_files(self, path: str, pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files in the source path matching the pattern. 
        Should return a list of dicts with at least 'file_name', 'file_size', 'path'."""
        pass

    @abstractmethod
    def download_file(self, remote_path: str, local_path: str) -> None:
        """Download file from source to a temporary local path."""
        pass

    @abstractmethod
    def get_metadata(self, remote_path: str) -> Dict[str, Any]:
        """Get file metadata."""
        pass

class DestinationConnector(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str) -> None:
        """Upload a local file to the destination."""
        pass

    @abstractmethod
    def create_directories(self, path: str) -> None:
        """Create target directories if they don't exist."""
        pass

    @abstractmethod
    def verify_file(self, remote_path: str, expected_size: int, expected_checksum: Optional[str] = None) -> bool:
        """Verify the file exists and matches size/checksum."""
        pass
