"""HDFS connector with two interchangeable transports.

`transport: cli` (default — matches the proven hadoopcli pattern):
    - Optional auto-`kinit -kt <keytab> <principal>` before each operation.
    - Runs `hadoopcli` (configurable binary) interactively over stdin:
          hadoopcli
          > copyFromLocal <local> <hdfs_dir>
          > exit
    - Uses the host's Hadoop config (core-site.xml / hdfs-site.xml) and Kerberos
      ticket cache. Native datanode addressing — no certificate / hostname dance.

`transport: webhdfs` (opt-in fallback):
    - Mirrors:  curl -L -k --negotiate -u : -X PUT -T <file>
                "https://<namenode>/webhdfs/v1/<path>?op=CREATE&overwrite=true"
    - SPNEGO/Kerberos via requests-kerberos. Two-step PUT (namenode -> 307 ->
      datanode). Useful when the host doesn't have a Hadoop client installed.

Per-job connection config:
    transport       cli (default) | webhdfs
    # Auth (used by both transports when present)
    principal       e.g. "sentinel@EXAMPLE.COM"
    keytab          path to keytab; if set with principal, runs kinit before each op
    krb5ccname      e.g. "FILE:/tmp/krb5cc_sentinel"  (optional ticket cache override)
    # CLI-specific
    hadoop_cli      binary name; default "hadoopcli"
    cli_timeout     seconds, default 600
    overwrite       true/false; if true and file exists, removed before upload (CLI mode)
    # WebHDFS-specific
    namenode        e.g. "https://nn.example.com:9871"
    kerberos        true/false (default true); false uses ?user.name=
    verify_ssl      true/false (default false; matches curl -k)
    user            for non-Kerberos clusters
"""
import os
import shlex
import subprocess
import urllib.parse
from typing import List, Dict, Any, Optional

import requests

from fileflow_agent.connectors.base import SourceConnector, DestinationConnector
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.utils.pattern import match_pattern

logger = get_logger("fileflow_agent.connectors.hdfs")


# ───────────────────────── shared helpers ─────────────────────────

def _transport(conn: Dict[str, Any]) -> str:
    """Return 'cli' or 'webhdfs'. Defaults to 'cli'."""
    t = (conn.get("transport") or "cli").lower()
    if t not in ("cli", "webhdfs"):
        raise ValueError(f"connection.transport must be 'cli' or 'webhdfs', got {t!r}")
    return t


def _build_env(conn: Dict[str, Any]) -> Dict[str, str]:
    """Copy os.environ + apply KRB5CCNAME override if configured."""
    env = os.environ.copy()
    if conn.get("krb5ccname"):
        env["KRB5CCNAME"] = conn["krb5ccname"]
    return env


def _kinit_if_configured(conn: Dict[str, Any]) -> None:
    """Refresh the Kerberos ticket from a keytab, if both keytab and principal
    are configured. Idempotent — safe to call before every operation."""
    keytab = conn.get("keytab")
    principal = conn.get("principal")
    if not keytab or not principal:
        return
    logger.info(f"kinit -kt {keytab} {principal}")
    result = subprocess.run(
        ["kinit", "-kt", keytab, principal],
        env=_build_env(conn),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"kinit failed (rc={result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )


# ───────────────────────── CLI transport ─────────────────────────

def _run_hadoopcli(commands: List[str], conn: Dict[str, Any]) -> str:
    """Pipe `commands` (one per line) into the configured hadoopcli binary,
    appending 'exit'. Returns stdout. Raises RuntimeError on non-zero exit."""
    binary = conn.get("hadoop_cli") or "hadoopcli"
    timeout = int(conn.get("cli_timeout") or 600)
    full_input = "\n".join(commands) + "\nexit\n"
    logger.info(f"{binary} <<< {' ; '.join(commands)}")
    result = subprocess.run(
        [binary],
        input=full_input,
        env=_build_env(conn),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{binary} failed (rc={result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def _cli_upload(local_path: str, remote_path: str, conn: Dict[str, Any]) -> None:
    """`copyFromLocal <local> <hdfs_dir>`. If overwrite, deletes the existing
    target first (hadoopcli copyFromLocal has no portable -f flag)."""
    _kinit_if_configured(conn)
    hdfs_dir = os.path.dirname(remote_path) or "/"
    cmds: List[str] = []
    if conn.get("overwrite", True):
        # rm -skipTrash returns nonzero if the file doesn't exist; we just don't
        # check the rc on the wrapper subprocess for this command. Easiest:
        # try rm in its own subprocess and ignore failure, then run copyFromLocal.
        try:
            _run_hadoopcli([f"rm -skipTrash {shlex.quote(remote_path)}"], conn)
        except RuntimeError as e:
            logger.debug(f"pre-upload rm of {remote_path} (likely nonexistent): {e}")
    cmds.append(f"copyFromLocal {shlex.quote(local_path)} {shlex.quote(hdfs_dir)}")
    _run_hadoopcli(cmds, conn)


def _cli_mkdirs(path: str, conn: Dict[str, Any]) -> None:
    if not path or path == "/":
        return
    _kinit_if_configured(conn)
    _run_hadoopcli([f"mkdir {shlex.quote(path)}"], conn)


def _cli_exists(path: str, conn: Dict[str, Any]) -> bool:
    _kinit_if_configured(conn)
    try:
        _run_hadoopcli([f"ls {shlex.quote(path)}"], conn)
        return True
    except RuntimeError as e:
        msg = str(e).lower()
        if "no such file" in msg or "does not exist" in msg or "file not found" in msg:
            return False
        raise  # genuine failure (auth, network, etc.)


def _cli_stat_size(path: str, conn: Dict[str, Any]) -> Optional[int]:
    """Try to get the file size in bytes from `ls -l <path>`. Returns None if
    we can't parse (non-fatal — caller may fall back to existence-only check)."""
    _kinit_if_configured(conn)
    try:
        out = _run_hadoopcli([f"ls -l {shlex.quote(path)}"], conn)
    except RuntimeError:
        return None
    # Typical line:  -rw-r--r--   3 user group     1234 2024-01-01 12:00 /path/to/file
    for line in out.splitlines():
        fields = line.split()
        if len(fields) >= 8 and fields[0].startswith("-"):
            try:
                return int(fields[4])
            except ValueError:
                continue
    return None


def _cli_list(path: str, pattern: Optional[str], conn: Dict[str, Any]) -> List[Dict[str, Any]]:
    _kinit_if_configured(conn)
    out = _run_hadoopcli([f"ls -l {shlex.quote(path)}"], conn)
    results: List[Dict[str, Any]] = []
    for line in out.splitlines():
        fields = line.split()
        # Files start with '-'; directories start with 'd' — skip dirs.
        if len(fields) < 8 or not fields[0].startswith("-"):
            continue
        try:
            size = int(fields[4])
        except ValueError:
            continue
        full = fields[-1]
        name = full.rsplit("/", 1)[-1]
        if not match_pattern(name, pattern):
            continue
        results.append({
            "file_name": name,
            "file_size": size,
            "path": full if full.startswith("/") else f"{path.rstrip('/')}/{name}",
        })
    return results


def _cli_download(remote_path: str, local_path: str, conn: Dict[str, Any]) -> None:
    _kinit_if_configured(conn)
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    _run_hadoopcli([f"copyToLocal {shlex.quote(remote_path)} {shlex.quote(local_path)}"], conn)


# ───────────────────────── WebHDFS transport ─────────────────────────

def _build_auth(conn: Dict[str, Any]):
    if not conn.get("kerberos", True):
        return None
    try:
        from requests_kerberos import HTTPKerberosAuth, DISABLED  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "WebHDFS Kerberos auth requires requests-kerberos. "
            "Install it or switch transport to 'cli'."
        ) from e
    return HTTPKerberosAuth(mutual_authentication=DISABLED)


def _hdfs_url(namenode: str, hdfs_path: str, op: str, conn: Dict[str, Any], **extra) -> str:
    base = namenode.rstrip("/")
    quoted = urllib.parse.quote(hdfs_path.lstrip("/"), safe="/")
    params = {"op": op, **{k: v for k, v in extra.items() if v is not None}}
    if not conn.get("kerberos", True) and conn.get("user"):
        params["user.name"] = conn["user"]
    return f"{base}/webhdfs/v1/{quoted}?{urllib.parse.urlencode(params)}"


def _request(method: str, url: str, conn: Dict[str, Any], **kwargs) -> requests.Response:
    verify = bool(conn.get("verify_ssl", False))
    if not verify:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    timeout = kwargs.pop("timeout", conn.get("timeout", 60))
    return requests.request(
        method, url,
        auth=_build_auth(conn),
        verify=verify,
        timeout=timeout,
        **kwargs,
    )


def _webhdfs_upload(local_path: str, remote_path: str, conn: Dict[str, Any]) -> None:
    nn_url = _hdfs_url(
        conn["namenode"], remote_path, "CREATE", conn,
        overwrite=str(conn.get("overwrite", True)).lower(),
    )
    r1 = _request("PUT", nn_url, conn, allow_redirects=False)
    if r1.status_code not in (307, 308):
        r1.raise_for_status()
        raise RuntimeError(
            f"WebHDFS CREATE expected 307 redirect, got {r1.status_code}: {r1.text[:200]}"
        )
    dn_url = r1.headers["Location"]
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


def _webhdfs_mkdirs(path: str, conn: Dict[str, Any]) -> None:
    if not path:
        return
    url = _hdfs_url(conn["namenode"], path, "MKDIRS", conn)
    r = _request("PUT", url, conn, allow_redirects=True)
    r.raise_for_status()


def _webhdfs_status(path: str, conn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Returns the FileStatus dict, or None if 404."""
    url = _hdfs_url(conn["namenode"], path, "GETFILESTATUS", conn)
    r = _request("GET", url, conn)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()["FileStatus"]


# ───────────────────────── connectors ─────────────────────────

class HDFSSourceConnector(SourceConnector):

    def list_files(self, path: str, pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.config.get("connection", {})
        if _transport(conn) == "cli":
            logger.info(f"hadoopcli ls {path}")
            results = _cli_list(path, pattern, conn)
        else:
            url = _hdfs_url(conn["namenode"], path, "LISTSTATUS", conn)
            logger.info(f"WebHDFS LISTSTATUS {path}")
            r = _request("GET", url, conn)
            r.raise_for_status()
            entries = r.json().get("FileStatuses", {}).get("FileStatus", [])
            results = [
                {"file_name": e["pathSuffix"], "file_size": int(e["length"]),
                 "path": f"{path.rstrip('/')}/{e['pathSuffix']}"}
                for e in entries
                if e.get("type") == "FILE" and match_pattern(e["pathSuffix"], pattern)
            ]
        logger.info(f"Found {len(results)} file(s) under {path}")
        return results

    def download_file(self, remote_path: str, local_path: str) -> None:
        conn = self.config.get("connection", {})
        logger.info(f"HDFS download {remote_path} -> {local_path}")
        if _transport(conn) == "cli":
            _cli_download(remote_path, local_path, conn)
        else:
            url = _hdfs_url(conn["namenode"], remote_path, "OPEN", conn)
            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
            with _request("GET", url, conn, stream=True, allow_redirects=True) as r:
                r.raise_for_status()
                with open(local_path, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            fh.write(chunk)

    def get_metadata(self, remote_path: str) -> Dict[str, Any]:
        conn = self.config.get("connection", {})
        if _transport(conn) == "cli":
            size = _cli_stat_size(remote_path, conn)
            return {"size": size if size is not None else 0}
        s = _webhdfs_status(remote_path, conn)
        if s is None:
            raise FileNotFoundError(remote_path)
        return {"size": int(s["length"]), "mtime": int(s["modificationTime"]) / 1000.0}


class HDFSDestinationConnector(DestinationConnector):

    def upload_file(self, local_path: str, remote_path: str) -> None:
        conn = self.config.get("connection", {})
        size = os.path.getsize(local_path)
        transport = _transport(conn)
        logger.info(
            f"HDFS upload [{transport}] {os.path.basename(local_path)} ({size} bytes) -> {remote_path}"
        )
        # Both transports want the parent dir to exist.
        parent = os.path.dirname(remote_path)
        if parent and parent != "/":
            self.create_directories(parent)
        if transport == "cli":
            _cli_upload(local_path, remote_path, conn)
        else:
            _webhdfs_upload(local_path, remote_path, conn)
        logger.info(f"Uploaded -> hdfs:{remote_path}")

    def create_directories(self, path: str) -> None:
        if not path:
            return
        conn = self.config.get("connection", {})
        if _transport(conn) == "cli":
            _cli_mkdirs(path, conn)
        else:
            _webhdfs_mkdirs(path, conn)

    def verify_file(self, remote_path: str, expected_size: int, expected_checksum: Optional[str] = None) -> bool:
        conn = self.config.get("connection", {})
        if _transport(conn) == "cli":
            if not _cli_exists(remote_path, conn):
                logger.warning(f"Verify failed: {remote_path} not found on HDFS")
                return False
            if expected_size == -1:
                return True
            actual = _cli_stat_size(remote_path, conn)
            if actual is None:
                logger.warning(f"Could not parse size for {remote_path}; treating as exists-only verify")
                return True
            match = actual == expected_size
            if not match:
                logger.error(f"Verify {remote_path}: expected={expected_size}, actual={actual}")
            return match
        # WebHDFS path
        s = _webhdfs_status(remote_path, conn)
        if s is None:
            logger.warning(f"Verify failed: {remote_path} not found on HDFS")
            return False
        if expected_size == -1:
            return True
        actual = int(s["length"])
        match = actual == expected_size
        if not match:
            logger.error(f"Verify {remote_path}: expected={expected_size}, actual={actual}")
        return match
