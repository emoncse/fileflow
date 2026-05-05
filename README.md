# FileFlow Agent

A modular, scheduler-driven data transfer platform built with Python. FileFlow automates the movement of files between configurable storage backends with support for cron scheduling, processing pipelines, deduplication, backup and retention policies.

## Features

- **Multi-backend connectors** — Local filesystem, SFTP, **S3-compatible** (AWS S3, DigitalOcean Spaces, Cloudflare R2, Backblaze B2, MinIO), **HDFS** (via `hadoopcli` + auto `kinit -kt`, or WebHDFS REST), SCP
- **Per-job, fully editable connections** — Each job carries its own connection block, so you can run multiple SFTPs, multiple S3 buckets across different providers, and multiple HDFS clusters side by side
- **Cron scheduling** — APScheduler with per-job cron expressions
- **Processing pipeline** — Compress (gzip / bzip2 / zip), decompress, prefix-rename, timestamp or chain a custom bash script
- **Deduplication** — SQLite-backed tracking prevents duplicate transfers across runs
- **Reliable backup & retention** — Configurable backup directories with automatic strict retention cleanup (NFS/CIFS-aware)
- **Transfer verification** — Size match, checksum, or existence-only checks
- **Web dashboard** — Responsive 'Soft UI' for realtime monitoring + form-based job editing (no YAML required); reload-on-save
- **REST API** — Health checks, transfer stats, job listing, and log streaming
- **OIDC-published wheels** — Distributed via PyPI Trusted Publishing (no long-lived tokens)

## Connectors

| Connector | Auth | Notes |
|---|---|---|
| `local` | n/a | Filesystem source/destination |
| `sftp` | password or key (incl. ssh-agent / `~/.ssh/id_*`) | Per-job host/port/user; auto `mkdir -p` on remote |
| `s3` | access_key+secret (per-job or env-var fallback) | Custom `endpoint_url` for any S3-compatible service; UI ships with provider presets for AWS, DigitalOcean Spaces (NYC3/SFO3/AMS3/FRA1/SGP1/BLR1/SYD1), Cloudflare R2, Backblaze B2, and MinIO; multipart upload via boto3 managed transfer |
| `hdfs` | Kerberos via `kinit -kt <keytab> <principal>` (auto-refreshed per op), or ambient ticket cache, or unsecured `?user.name=` | **CLI transport** (default): drives `hadoopcli` over stdin (`copyFromLocal`, `copyToLocal`, `mkdir`, `ls`, `rm`); reads `core-site.xml`/`hdfs-site.xml` from the host. **WebHDFS transport** (opt-in): pure REST (`op=CREATE` + 307 → datanode), no Hadoop client needed |
| `scp` | _stub_ | Reserved for future implementation |

## Architecture

```
├── configs/                # YAML job definitions
│   ├── jobs.yaml
│   └── test_jobs.yaml
├── src/fileflow_agent/
│   ├── api/                # FastAPI endpoints + dashboard serving
│   ├── config/             # Pydantic models and settings loader
│   ├── connectors/         # Source/Destination connector implementations
│   ├── logging/            # Structured rotating logger
│   ├── processing/         # File processing pipeline
│   ├── scheduler/          # APScheduler integration
│   ├── services/           # Transfer, backup, retention, verification
│   ├── static/             # Dashboard frontend (HTML/CSS/JS)
│   ├── tracking/           # SQLite transfer history & deduplication
│   ├── utils/              # Checksum utilities
│   └── main.py             # Application entrypoint
├── test_*.py               # Unit and integration tests
├── .env.example
├── run.sh                  # Easy startup script
├── pyproject.toml
├── requirements.txt
└── README.md
```


## Getting Started

### Prerequisites

- Python 3.10+
- `pip`

### Installation & Workspace Setup

FileFlow Agent is designed as a standalone global Pip library. When you install it, it gives your system a new command-line tool `fileflow`.

```bash
# 1. Install via Pip (In a virtual environment or globally)
pip install fileflow-agent

# 2. Initialize a secure Workspace
# This creates localized databases, configuration templates, and log directories.
fileflow init ~/my_fileflow_workspace

# 3. Start the Agent from the configured workspace
fileflow start ~/my_fileflow_workspace --port 7345
```

Once running, open `http://localhost:7345` to access the Neumorphic monitoring dashboard.

### Configuration

The `fileflow init` command will automatically scaffold a `.env` and `configs/jobs.yaml` in your chosen workspace directory.

1. **Environment Config (`~/my_fileflow_workspace/.env`)**
   Set your UI authentication credentials and global AWS/SFTP master keys if needed.

2. **Job Config (`~/my_fileflow_workspace/configs/jobs.yaml`)**
   *(You can edit this file manually, or configure jobs entirely from the Web Dashboard without touching YAML!)*

YAML job definitions look like this — **everything is also editable from the dashboard**, so you don't have to hand-write any of it:

```yaml
jobs:
  # AWS S3 (default — endpoint omitted, region us-east-1)
  - job_id: daily_backup_aws
    enabled: true
    schedule: "0 */6 * * *"
    source:
      type: local
      path: /data/incoming
      file_pattern: "*.csv"
    destination:
      type: s3
      path: archive/csv
      connection:
        bucket: my-bucket
        region: us-east-2
        # access_key/secret_key omitted -> falls back to AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env
    processing:
      enabled: true
      steps: [compress, timestamp]
    backup:
      enabled: true
      location: backups/daily
      retention_days: 30
    verification:
      method: size_match

  # DigitalOcean Spaces (or any S3-compatible: just set endpoint_url)
  - job_id: nightly_to_do_spaces
    enabled: true
    schedule: "0 2 * * *"
    source: { type: local, path: /var/log/app, file_pattern: "*.log.gz" }
    destination:
      type: s3
      path: app-logs
      connection:
        endpoint_url: "https://nyc2.digitaloceanspaces.com"
        region: nyc3
        bucket: my-space
    verification: { method: size_match }

  # Local -> HDFS via hadoopcli (auto kinit -kt; production-friendly)
  - job_id: events_to_hdfs
    enabled: true
    schedule: "*/5 * * * *"
    source: { type: local, path: /var/tmp, file_pattern: "*.gz" }
    destination:
      type: hdfs
      path: /external/
      connection:
        transport: cli                              # default; reads core-site.xml from the host
        principal: "example@EXAMPLE.COM"
        keytab: "/home/example/example.kt"        # auto kinit -kt before each upload
        krb5ccname: "FILE:/tmp/k5cc_example"
        hadoop_cli: hadoopcli
        overwrite: true                             # rm -skipTrash, then copyFromLocal
    verification: { method: size_match }
```

The built-in Neumorphic web dashboard provides:

| View | Description |
|---|---|
| **Overview** | Transfer stats (total, success, failed, duplicates) and recent transfer table |
| **Configuration** | Form-based job editor — add, edit, delete jobs and reload the scheduler live |
| **System Logs** | Real-time log viewer with auto-refresh |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/jobs` | List configured jobs |
| `GET` | `/transfers` | Recent transfer records |
| `GET` | `/stats/summary` | Aggregated transfer statistics |
| `GET` | `/logs/recent` | Recent log entries |
| `GET` | `/api/config` | Read raw YAML config |
| `POST` | `/api/config` | Save config and reload scheduler |

## Extending Connectors

Implement `SourceConnector` or `DestinationConnector` from `connectors/base.py` and register in `connectors/factory.py`:

```python
from fileflow_agent.connectors.base import SourceConnector

class MySourceConnector(SourceConnector):
    def list_files(self, path, pattern=None):
        ...

    def download_file(self, remote_path, local_path):
        ...

    def get_metadata(self, remote_path):
        ...
```

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

1. Fork the repository (https://github.com/emoncse/fileflow)
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source and available under the [MIT License](LICENSE).
