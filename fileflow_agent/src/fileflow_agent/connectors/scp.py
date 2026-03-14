from typing import List, Dict, Any, Optional
from fileflow_agent.connectors.base import SourceConnector, DestinationConnector

class SCPSourceConnector(SourceConnector):
    def list_files(self, path: str, pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        return []
    def download_file(self, remote_path: str, local_path: str) -> None:
        pass
    def get_metadata(self, remote_path: str) -> Dict[str, Any]:
        return {}

class SCPDestinationConnector(DestinationConnector):
    def upload_file(self, local_path: str, remote_path: str) -> None:
        pass
    def create_directories(self, path: str) -> None:
        pass
    def verify_file(self, remote_path: str, expected_size: int, expected_checksum: Optional[str] = None) -> bool:
        return True
