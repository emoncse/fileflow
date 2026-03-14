from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import yaml
import json
from typing import Dict, Any, List
import os
from pathlib import Path

from fileflow_agent.tracking.repository import TrackingRepository
from fileflow_agent.config.settings import load_settings, load_jobs_config

app = FastAPI(title="FileFlow Agent Monitoring API")
repo = TrackingRepository()
_scheduler = None

STATIC_DIR = str(Path(__file__).resolve().parent.parent / "static")


def set_scheduler(scheduler):
    global _scheduler
    _scheduler = scheduler

def get_jobs_config():
    config_path = os.environ.get("FILEFLOW_JOBS_CONFIG", "configs/jobs.yaml")
    try:
        return load_jobs_config(config_path)
    except FileNotFoundError:
        return None


@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/jobs")
def get_jobs():
    config = get_jobs_config()
    if not config:
        return {"jobs": []}
    return {"jobs": [job.model_dump() for job in config.jobs]}

@app.get("/transfers")
def get_recent_transfers(limit: int = 50):
    transfers = repo.get_recent_transfers(limit=limit)
    return {"transfers": transfers}

@app.get("/stats/summary")
def get_stats_summary():
    stats = repo.get_stats()
    return stats

@app.get("/logs/recent")
def get_recent_logs(lines: int = 100):
    log_file = "logs/fileflow.log"
    if not os.path.exists(log_file):
        return {"logs": []}
    try:
        with open(log_file, "r") as f:
            content = f.readlines()
            return {"logs": content[-lines:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
def get_config_raw():
    config_path = os.environ.get("FILEFLOW_JOBS_CONFIG", "configs/jobs.yaml")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="Config file not found")
    with open(config_path, "r") as f:
        return {"content": f.read()}

@app.post("/api/config")
async def save_config_raw(request: Request):
    data = await request.json()
    content = data.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="Missing 'content'")

    config_path = os.environ.get("FILEFLOW_JOBS_CONFIG", "configs/jobs.yaml")

    try:
        yaml.safe_load(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")

    try:
        with open(config_path, "w") as f:
            f.write(content)

        if _scheduler:
            new_config = load_jobs_config(config_path)
            _scheduler.clear_jobs()
            _scheduler.load_jobs_from_config(new_config)

        return {"status": "success", "message": "Configuration updated and applied"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def serve_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
