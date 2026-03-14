# FileFlow Agent

A modular, scheduler-driven data transfer platform built with Python. FileFlow automates the movement of files between configurable storage backends with support for cron scheduling, processing pipelines, deduplication, backup, and retention policies.

## Features

- **Multi-backend connectors** — Local filesystem, SFTP, AWS S3, SCP, HDFS
- **Cron scheduling** — APScheduler with per-job cron expressions
- **Processing pipeline** — Compress, decompress, and rename files in transit
- **Deduplication** — SQLite-backed tracking to prevent duplicate transfers
- **Backup & retention** — Configurable backup location with automatic cleanup
- **Transfer verification** — Size match, checksum, and existence checks
- **Web dashboard** — Real-time monitoring UI with job configuration management
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
├── pyproject.toml
├── requirements.txt
└── README.md
```


## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
git clone git@github.com:emoncse/fileflow.git
cd fileflow
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Configuration

1. Copy and edit the environment file:

```bash
cp .env.example .env
```

2. Define jobs in `configs/jobs.yaml`:

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

### Running

```bash
python src/fileflow_agent/main.py --config configs/jobs.yaml --port 8000
```

This starts the scheduler and the API server. Open `http://localhost:8000` for the monitoring dashboard.

## Dashboard

The built-in dashboard provides:

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
