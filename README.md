# FileFlow Agent

A modular, scheduler-driven data transfer platform built with Python. FileFlow automates the movement of files between configurable storage backends with support for cron scheduling, processing pipelines, deduplication, backup, and retention policies.

## Features

- **Multi-backend connectors** — Local filesystem, SFTP, AWS S3, SCP, HDFS
- **Advanced Job Configuration** — Define standalone connection properties (Host, Port, User, Password) independently per job, enabling multiple distinct SFTP transfers
- **Cron scheduling** — APScheduler with per-job cron expressions
- **Processing pipeline** — Compress, decompress, and rename files in transit
- **Deduplication** — SQLite-backed tracking to prevent duplicate transfers
- **Reliable backup & retention** — Configurable backup directories with automatic strict retention cleanup
- **Transfer verification** — Size match, checksum, and existence checks
- **Neumorphic Dashboard** — Responsive, clean 'Soft UI' realtime monitoring and config management interface
- **REST API** — Health checks, transfer stats, job listing, and log streaming

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
fileflow start ~/my_fileflow_workspace --port 8000
```

Once running, open `http://localhost:8000` to access the Neumorphic monitoring dashboard.

### Configuration

The `fileflow init` command will automatically scaffold a `.env` and `configs/jobs.yaml` in your chosen workspace directory.

1. **Environment Config (`~/my_fileflow_workspace/.env`)**
   Set your UI authentication credentials and global AWS/SFTP master keys if needed.

2. **Job Config (`~/my_fileflow_workspace/configs/jobs.yaml`)**
   *(You can edit this file manually, or configure jobs entirely from the Web Dashboard without touching YAML!)*

This is what a YAML job definition looks like:

```yaml
jobs:
  - job_id: daily_backup
    enabled: true
    schedule: "0 */6 * * *"

    source:
      type: local
      path: /data/incoming
      file_pattern: "*.csv"

    destination:
      type: s3
      path: archive/csv
      bucket: my-bucket

    processing:
      enabled: true
      steps:
        - compress

    backup:
      enabled: true
      location: backups/daily
      retention_days: 30

    verification:
      method: size_match
```

*(You can also configure jobs entirely from the Web Dashboard without touching YAML!)*

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

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source and available under the [MIT License](LICENSE).
