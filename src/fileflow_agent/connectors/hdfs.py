"""WebHDFS connector.

Mirrors the canonical curl upload pattern used against secured Hadoop clusters:

    curl -L -k --negotiate -u : -X PUT -T <local> \
         "https://<namenode>:<port>/webhdfs/v1/<path>?op=CREATE&overwrite=true"

Flag mapping:
    -L            -> two-step PUT: namenode returns 307 with datanode Location
    -k            -> connection.verify_ssl: false  (urllib3 InsecureRequestWarning suppressed)
    --negotiate   -> connection.kerberos: true     (SPNEGO via requests-kerberos)
    -u :          -> empty principal, ticket comes from the ambient kinit cache
    -X PUT -T     -> requests.put(..., data=fh)
    op=CREATE...  -> WebHDFS REST API parameters
"""
import os
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple

import requests
from fileflow_agent.connectors.base import SourceConnector, DestinationConnector
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.utils.pattern import match_pattern

logger = get_logger("fileflow_agent.connectors.hdfs")


def _build_auth(conn: Dict[str, Any]):
    """Return a requests auth object based on connection config.

    kerberos: true (default)  -> SPNEGO/Kerberos via requests-kerberos (matches `--negotiate -u :`)
    kerberos: false           -> None; caller appends ?user.name=<user> for unsecured clusters
    """
    if not conn.get("kerberos", True):
        return None
    try:
        from requests_kerberos import HTTPKerberosAuth, DISABLED  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Kerberos auth requires the 'requests-kerberos' package. "
            "Install it (and its system Kerberos libs) or set connection.kerberos: false."
        ) from e
    # mutual_authentication=DISABLED matches curl --negotiate behaviour: many WebHDFS
    # datanodes don't return a server-token on 201 responses.
    return HTTPKerberosAuth(mutual_authentication=DISABLED)


def _hdfs_url(namenode: str, hdfs_path: str, op: str, conn: Dict[str, Any], **extra) -> str:
    """Build a /webhdfs/v1/<path>?op=<op>&... URL."""
    base = namenode.rstrip("/")
    quoted = urllib.parse.quote(hdfs_path.lstrip("/"), safe="/")
    params = {"op": op, **{k: v for k, v in extra.items() if v is not None}}
    if not conn.get("kerberos", True) and conn.get("user"):
        params["user.name"] = conn["user"]
    return f"{base}/webhdfs/v1/{quoted}?{urllib.parse.urlencode(params)}"


def _request(method: str, url: str, conn: Dict[str, Any], **kwargs) -> requests.Response:
    verify = bool(conn.get("verify_ssl", False))
    if not verify:
        # Suppress the InsecureRequestWarning spam when -k is used, just like curl.
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    timeout = kwargs.pop("timeout", conn.get("timeout", 60))
    return requests.request(
        method,
        url,
        auth=_build_auth(conn),
        verify=verify,
        timeout=timeout,
        **kwargs,
    )


def _join_hdfs(directory: str, name: str) -> str:
    return f"{directory.rstrip('/')}/{name}"


class HDFSSourceConnector(SourceConnector):

    def list_files(self, path: str, pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.config.get("connection", {})
        url = _hdfs_url(conn["namenode"], path, "LISTSTATUS", conn)
        logger.info(f"WebHDFS LISTSTATUS {path}")
        r = _request("GET", url, conn)
        r.raise_for_status()
        entries = r.json().get("FileStatuses", {}).get("FileStatus", [])
        results: List[Dict[str, Any]] = []
        for e in entries:
            if e.get("type") != "FILE":
                continue
            name = e["pathSuffix"]
            if not match_pattern(name, pattern):
                continue
            results.append({
                "file_name": name,
                "file_size": int(e["length"]),
                "path": _join_hdfs(path, name),
            })
        logger.info(f"Found {len(results)} file(s) under {path}")
        return results

    def download_file(self, remote_path: str, local_path: str) -> None:
        conn = self.config.get("connection", {})
        url = _hdfs_url(conn["namenode"], remote_path, "OPEN", conn)
        logger.info(f"WebHDFS OPEN {remote_path} -> {local_path}")
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with _request("GET", url, conn, stream=True, allow_redirects=True) as r:
            r.raise_for_status()
            with open(local_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)

    def get_metadata(self, remote_path: str) -> Dict[str, Any]:
        conn = self.config.get("connection", {})
        url = _hdfs_url(conn["namenode"], remote_path, "GETFILESTATUS", conn)
        r = _request("GET", url, conn)
        r.raise_for_status()
        s = r.json()["FileStatus"]
        return {"size": int(s["length"]), "mtime": int(s["modificationTime"]) / 1000.0}


class HDFSDestinationConnector(DestinationConnector):

    def upload_file(self, local_path: str, remote_path: str) -> None:
        """Two-step WebHDFS PUT.

        1. PUT to namenode with no body, allow_redirects=False -> 307 with datanode Location
        2. PUT the file body to the datanode URL -> 201 Created
        """
        conn = self.config.get("connection", {})
        size = os.path.getsize(local_path)
        logger.info(
            f"WebHDFS CREATE {os.path.basename(local_path)} ({size} bytes) -> {remote_path}"
        )

        # Make sure the parent directory exists; many clusters won't auto-create it.
        parent = os.path.dirname(remote_path)
        if parent and parent != "/":
            self.create_directories(parent)

        # Step 1: hit the namenode, do NOT follow the redirect — we want to re-issue
        # the PUT against the datanode with the file body.
        nn_url = _hdfs_url(
            conn["namenode"], remote_path, "CREATE", conn,
            overwrite=str(conn.get("overwrite", True)).lower(),
        )
        r1 = _request("PUT", nn_url, conn, allow_redirects=False)
        if r1.status_code not in (307, 308):
            r1.raise_for_status()
            raise RuntimeError(
                f"WebHDFS CREATE expected 307 redirect from namenode, got {r1.status_code}: {r1.text[:200]}"
            )
        dn_url = r1.headers["Location"]
        logger.debug(f"Datanode redirect: {dn_url}")

        # Step 2: stream the file to the datanode.
        with open(local_path, "rb") as fh:
            r2 = _request(
                "PUT", dn_url, conn,
                data=fh,
                headers={"Content-Type": "application/octet-stream"},
                allow_redirects=False,
            )
        if r2.status_code != 201:
            raise RuntimeError(
                f"WebHDFS CREATE upload failed: {r2.status_code} {r2.text[:200]}"
            )
        logger.info(f"Uploaded {os.path.basename(local_path)} -> {remote_path}")

    def create_directories(self, path: str) -> None:
        if not path:
            return
        conn = self.config.get("connection", {})
        url = _hdfs_url(conn["namenode"], path, "MKDIRS", conn)
        r = _request("PUT", url, conn, allow_redirects=True)
        r.raise_for_status()

    def verify_file(self, remote_path: str, expected_size: int, expected_checksum: Optional[str] = None) -> bool:
        conn = self.config.get("connection", {})
        url = _hdfs_url(conn["namenode"], remote_path, "GETFILESTATUS", conn)
        r = _request("GET", url, conn)
        if r.status_code == 404:
            logger.warning(f"Verify failed: {remote_path} not found on HDFS")
            return False
        r.raise_for_status()
        actual = int(r.json()["FileStatus"]["length"])
        if expected_size == -1:
            return True
        match = actual == expected_size
        if not match:
            logger.error(
                f"Verify {remote_path}: expected={expected_size}, actual={actual}"
            )
        return match
