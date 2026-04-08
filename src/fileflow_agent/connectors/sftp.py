import os
import fnmatch
import stat
from typing import List, Dict, Any, Optional, Tuple

import paramiko

from fileflow_agent.connectors.base import SourceConnector, DestinationConnector
from fileflow_agent.logging.logger import get_logger

logger = get_logger("fileflow_agent.connectors.sftp")


def _create_sftp_connection(conn: Dict[str, Any]) -> Tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    """Creates a paramiko SSH+SFTP connection.

    Auth order (same as normal SSH client behaviour):
      1. Explicit password  — if 'password' is set in connection config
      2. Explicit key_file  — if 'key_file' is set in connection config
      3. SSH agent          — paramiko tries the running ssh-agent automatically
      4. Default key files  — paramiko scans ~/.ssh/id_rsa, id_ed25519, id_ecdsa, id_dsa

    Steps 3 & 4 happen automatically via allow_agent=True + look_for_keys=True.
    """
    host = conn.get('host', 'localhost')
    port = int(conn.get('port', 22))
    username = conn.get('username', None)
    password = conn.get('password', None)
    key_file = conn.get('key_file', None)

    auth_desc = 'password' if password else (f'key:{key_file}' if key_file else 'auto (agent/default keys)')
    logger.info(f"Connecting to SFTP {username}@{host}:{port} — auth: {auth_desc}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: Dict[str, Any] = dict(
        hostname=host,
        port=port,
        username=username,
        allow_agent=True,    # try running ssh-agent automatically
        look_for_keys=True,  # scan ~/.ssh/id_rsa, id_ed25519, id_ecdsa, id_dsa
    )

    if password:
        connect_kwargs['password'] = password
    if key_file:
        connect_kwargs['key_filename'] = key_file

    try:
        ssh.connect(**connect_kwargs)
    except paramiko.AuthenticationException as e:
        logger.error(
            f"SFTP authentication failed for {username}@{host}:{port} "
            f"(auth={auth_desc}). "
            f"Check password / SSH key. Detail: {e}"
        )
        raise
    except paramiko.SSHException as e:
        logger.error(f"SFTP SSH error connecting to {host}:{port}: {e}")
        raise
    except OSError as e:
        logger.error(f"SFTP network error connecting to {host}:{port}: {e}")
        raise

    logger.info(f"SFTP connection established: {username}@{host}:{port}")
    sftp = ssh.open_sftp()
    return ssh, sftp


class SFTPSourceConnector(SourceConnector):

    def list_files(self, path: str, pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.config.get('connection', {})
        host = conn.get('host', 'unknown_host')
        logger.info(f"Listing files on SFTP server: {host} at {path}")

        ssh, sftp = _create_sftp_connection(conn)
        try:
            results = []
            for entry in sftp.listdir_attr(path):
                if not stat.S_ISREG(entry.st_mode):
                    continue
                name = entry.filename
                if pattern and not fnmatch.fnmatch(name, pattern):
                    continue
                results.append({
                    'file_name': name,
                    'file_size': entry.st_size,
                    'path': f"{path.rstrip('/')}/{name}",
                })
            logger.info(f"Found {len(results)} file(s) on {host}:{path}")
            return results
        finally:
            sftp.close()
            ssh.close()

    def download_file(self, remote_path: str, local_path: str) -> None:
        conn = self.config.get('connection', {})
        host = conn.get('host', 'unknown_host')
        logger.info(f"Downloading {remote_path} from SFTP server: {host}")
        ssh, sftp = _create_sftp_connection(conn)
        try:
            sftp.get(remote_path, local_path)
            logger.info(f"Downloaded {remote_path} -> {local_path}")
        finally:
            sftp.close()
            ssh.close()

    def get_metadata(self, remote_path: str) -> Dict[str, Any]:
        conn = self.config.get('connection', {})
        ssh, sftp = _create_sftp_connection(conn)
        try:
            attr = sftp.stat(remote_path)
            return {'size': attr.st_size, 'mtime': attr.st_mtime}
        finally:
            sftp.close()
            ssh.close()


class SFTPDestinationConnector(DestinationConnector):

    def upload_file(self, local_path: str, remote_path: str) -> None:
        conn = self.config.get('connection', {})
        host = conn.get('host', 'unknown_host')
        logger.info(f"Uploading file to SFTP server: {host} at {remote_path}")

        ssh, sftp = _create_sftp_connection(conn)
        try:
            # Ensure remote directory exists before uploading
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                _ensure_remote_dir(sftp, remote_dir)
            sftp.put(local_path, remote_path)
            logger.info(f"Successfully uploaded {os.path.basename(local_path)} -> {host}:{remote_path}")
        finally:
            sftp.close()
            ssh.close()

    def create_directories(self, path: str) -> None:
        conn = self.config.get('connection', {})
        ssh, sftp = _create_sftp_connection(conn)
        try:
            _ensure_remote_dir(sftp, path)
        finally:
            sftp.close()
            ssh.close()

    def verify_file(self, remote_path: str, expected_size: int, expected_checksum: Optional[str] = None) -> bool:
        conn = self.config.get('connection', {})
        host = conn.get('host', 'unknown_host')
        ssh, sftp = _create_sftp_connection(conn)
        try:
            attr = sftp.stat(remote_path)
            match = attr.st_size == expected_size
            logger.debug(f"Verify {host}:{remote_path} — expected={expected_size}, actual={attr.st_size}, match={match}")
            return match
        except FileNotFoundError:
            logger.warning(f"Verify failed: {remote_path} not found on {host}")
            return False
        finally:
            sftp.close()
            ssh.close()


def _ensure_remote_dir(sftp: paramiko.SFTPClient, path: str) -> None:
    """Recursively create remote directory path (like mkdir -p)."""
    parts = [p for p in path.strip('/').split('/') if p]
    current = '/' if path.startswith('/') else ''
    for part in parts:
        current = f"{current}/{part}" if current else part
        try:
            sftp.stat(current)
        except FileNotFoundError:
            logger.debug(f"Creating remote directory: {current}")
            sftp.mkdir(current)
