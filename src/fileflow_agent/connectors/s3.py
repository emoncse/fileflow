"""S3 connector — works with AWS S3 and any S3-compatible service (DigitalOcean
Spaces, Cloudflare R2, MinIO, Backblaze B2 S3, …) by setting endpoint_url.

Per-job connection config (all optional except endpoint_url for non-AWS):
    endpoint_url   e.g. https://nyc3.digitaloceanspaces.com  (omit for AWS)
    region         e.g. nyc3 / us-east-1                     (falls back to env AWS_REGION)
    access_key     falls back to env AWS_ACCESS_KEY_ID
    secret_key     falls back to env AWS_SECRET_ACCESS_KEY
    bucket         the bucket name; for destination also accepted as top-level config.bucket
    verify_ssl     default True

.s3cfg field mapping:
    access_key       -> connection.access_key
    secret_key       -> connection.secret_key
    host_base + use_https -> connection.endpoint_url   (e.g. https://nyc3.digitaloceanspaces.com)
    bucket_location  -> connection.region
"""
import os
from typing import List, Dict, Any, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from fileflow_agent.connectors.base import SourceConnector, DestinationConnector
from fileflow_agent.config.settings import load_settings
from fileflow_agent.logging.logger import get_logger
from fileflow_agent.utils.pattern import match_pattern

logger = get_logger("fileflow_agent.connectors.s3")


def _get_bucket(config: Dict[str, Any]) -> str:
    """Read bucket from connection.bucket, falling back to top-level config.bucket
    (destination-style). Raises if neither is set."""
    bucket = config.get("connection", {}).get("bucket") or config.get("bucket")
    if not bucket:
        raise ValueError("S3 connector requires a bucket (set connection.bucket or destination.bucket)")
    return bucket


def _build_client(connection: Dict[str, Any]):
    """Construct a boto3 S3 client, layering per-job config over env defaults."""
    settings = load_settings()
    kwargs: Dict[str, Any] = {}

    endpoint = connection.get("endpoint_url")
    if endpoint:
        kwargs["endpoint_url"] = endpoint

    region = connection.get("region") or settings.aws_region
    if region:
        kwargs["region_name"] = region

    access_key = connection.get("access_key") or settings.aws_access_key
    secret_key = connection.get("secret_key") or settings.aws_secret_key
    if access_key:
        kwargs["aws_access_key_id"] = access_key
    if secret_key:
        kwargs["aws_secret_access_key"] = secret_key

    if connection.get("verify_ssl") is False:
        kwargs["verify"] = False

    # Most S3-compatible providers (DO Spaces, R2, MinIO) require s3v4.
    # We also allow opt-in for path-style addressing.
    s3_opts = {}
    if connection.get("addressing_style") == "path":
        s3_opts["addressing_style"] = "path"

    kwargs["config"] = BotoConfig(
        signature_version="s3v4",
        s3=s3_opts
    )

    return boto3.client("s3", **kwargs)


class S3SourceConnector(SourceConnector):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = _build_client(config.get("connection", {}))
        self.bucket = _get_bucket(config)

    def list_files(self, path: str, pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        prefix = path.strip("/")
        if prefix:
            prefix = prefix + "/"
        logger.info(f"Listing s3://{self.bucket}/{prefix} (pattern={pattern})")
        results: List[Dict[str, Any]] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter="/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Skip "directory marker" zero-byte keys ending in /
                if key.endswith("/"):
                    continue
                name = key.rsplit("/", 1)[-1]
                if not match_pattern(name, pattern):
                    continue
                results.append({
                    "file_name": name,
                    "file_size": int(obj["Size"]),
                    "path": key,
                })
        logger.info(f"Found {len(results)} object(s) in s3://{self.bucket}/{prefix}")
        return results

    def download_file(self, remote_path: str, local_path: str) -> None:
        key = remote_path.lstrip("/")
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        logger.info(f"Downloading s3://{self.bucket}/{key} -> {local_path}")
        # boto3 handles ranged multipart download under the hood for large objects.
        self.client.download_file(self.bucket, key, local_path)

    def get_metadata(self, remote_path: str) -> Dict[str, Any]:
        key = remote_path.lstrip("/")
        head = self.client.head_object(Bucket=self.bucket, Key=key)
        return {
            "size": int(head["ContentLength"]),
            "mtime": head["LastModified"].timestamp(),
            "etag": head.get("ETag", "").strip('"'),
        }


class S3DestinationConnector(DestinationConnector):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = _build_client(config.get("connection", {}))
        self.bucket = _get_bucket(config)

    def upload_file(self, local_path: str, remote_path: str) -> None:
        # transfer_service hands us the full key as `<dest.path>/<file>` — just strip
        # any leading slash since S3 keys never start with /.
        key = remote_path.lstrip("/")
        size = os.path.getsize(local_path)
        logger.info(f"Uploading {os.path.basename(local_path)} ({size} bytes) -> s3://{self.bucket}/{key}")
        # upload_file uses managed transfer: multipart for large files, retries built-in.
        self.client.upload_file(local_path, self.bucket, key)
        logger.info(f"Uploaded -> s3://{self.bucket}/{key}")

    def create_directories(self, path: str) -> None:
        # S3 has no real directories — keys with "/" are virtual paths.
        # No-op: the prefix is implicit when the first object is uploaded.
        return

    def verify_file(self, remote_path: str, expected_size: int, expected_checksum: Optional[str] = None) -> bool:
        key = remote_path.lstrip("/")
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                logger.warning(f"Verify failed: s3://{self.bucket}/{key} not found")
                return False
            raise
        if expected_size == -1:
            return True
        actual = int(head["ContentLength"])
        match = actual == expected_size
        if not match:
            logger.error(f"Verify s3://{self.bucket}/{key}: expected={expected_size}, actual={actual}")
        return match
