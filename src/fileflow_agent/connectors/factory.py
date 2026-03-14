from fileflow_agent.connectors.base import SourceConnector, DestinationConnector
from fileflow_agent.connectors.local import LocalSourceConnector, LocalDestinationConnector
from fileflow_agent.connectors.s3 import S3SourceConnector, S3DestinationConnector
from fileflow_agent.connectors.sftp import SFTPSourceConnector, SFTPDestinationConnector
from fileflow_agent.connectors.scp import SCPSourceConnector, SCPDestinationConnector
from fileflow_agent.connectors.hdfs import HDFSSourceConnector, HDFSDestinationConnector
from fileflow_agent.config.models import ConnectorType
from typing import Dict, Any

class ConnectorFactory:
    @staticmethod
    def get_source_connector(connector_type: ConnectorType, config: Dict[str, Any]) -> SourceConnector:
        if connector_type == ConnectorType.LOCAL:
            return LocalSourceConnector(config)
        elif connector_type == ConnectorType.S3:
            return S3SourceConnector(config)
        elif connector_type == ConnectorType.SFTP:
            return SFTPSourceConnector(config)
        elif connector_type == ConnectorType.SCP:
            return SCPSourceConnector(config)
        elif connector_type == ConnectorType.HDFS:
            return HDFSSourceConnector(config)
        else:
            raise ValueError(f"Unknown source connector type: {connector_type}")

    @staticmethod
    def get_destination_connector(connector_type: ConnectorType, config: Dict[str, Any]) -> DestinationConnector:
        if connector_type == ConnectorType.LOCAL:
            return LocalDestinationConnector(config)
        elif connector_type == ConnectorType.S3:
            return S3DestinationConnector(config)
        elif connector_type == ConnectorType.SFTP:
            return SFTPDestinationConnector(config)
        elif connector_type == ConnectorType.SCP:
            return SCPDestinationConnector(config)
        elif connector_type == ConnectorType.HDFS:
            return HDFSDestinationConnector(config)
        else:
            raise ValueError(f"Unknown destination connector type: {connector_type}")
