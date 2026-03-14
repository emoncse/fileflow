import os
from typing import Optional
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.config.models import VerificationMethod, VerificationConfig
from fileflow_agent.connectors.base import DestinationConnector
from fileflow_agent.utils.checksum import calculate_checksum

logger = get_logger("fileflow_agent.services.verification_service")

class VerificationService:
    def verify(self, 
               remote_path: str, 
               local_path: str,
               connector: DestinationConnector,
               config: Optional[VerificationConfig]) -> bool:
        
        if not config:
            logger.info("Verification not configured. Skipping.")
            return True
            
        method = config.method
        
        if method == VerificationMethod.EXISTS:
            logger.info("Verifying file exists")
            return connector.verify_file(remote_path, expected_size=-1) # -1 can mean skip size check
            
        expected_size = os.path.getsize(local_path)
        expected_checksum = None
        
        if method == VerificationMethod.CHECKSUM:
            logger.info("Calculating expected checksum for verification")
            expected_checksum = calculate_checksum(local_path)
            
        logger.info(f"Verifying using method {method}")
        return connector.verify_file(remote_path, expected_size, expected_checksum)
