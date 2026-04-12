from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import yaml
import json
import stat
import shutil
from typing import Dict, Any, List
import os
from pathlib import Path

from fileflow_agent.tracking.repository import TrackingRepository
from fileflow_agent.config.settings import load_settings, load_jobs_config
from fileflow_agent.api.auth import (
    create_token, verify_token,
    get_current_user, require_admin,
    USERS,
)

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
    except Exception as e:
        import logging
        logging.getLogger("fileflow_agent.api").error(f"Failed to load jobs config: {e}")
        return None


# ── Auth endpoints (public) ───────────────────────────────────────────────────

@app.post("/api/auth/login")
async def login(request: Request):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = USERS.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_token(username, user["role"])
    return {"token": token, "username": username, "role": user["role"]}


@app.get("/api/auth/me")
def whoami(user: dict = Depends(get_current_user)):
    return user


# ── Read-only endpoints (any authenticated user) ──────────────────────────────

@app.get("/health")
def health_check(user: dict = Depends(get_current_user)):
    return {"status": "healthy"}

@app.get("/jobs")
def get_jobs(user: dict = Depends(get_current_user)):
    config = get_jobs_config()
    if not config:
        return {"jobs": []}
    return {"jobs": [job.model_dump() for job in config.jobs]}

@app.get("/transfers")
def get_recent_transfers(
    page: int = 1,
    page_size: int = 20,
    job_id: str = None,
    file_name: str = None,
    status: str = None,
    date_from: str = None,
    date_to: str = None,
    source_type: str = None,
    dest_type: str = None,
    user: dict = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    return repo.get_recent_transfers(
        limit=page_size,
        offset=offset,
        job_id=job_id,
        file_name=file_name,
        status=status,
        date_from=date_from,
        date_to=date_to,
        source_type=source_type,
        dest_type=dest_type,
    )

@app.get("/stats/summary")
def get_stats_summary(user: dict = Depends(get_current_user)):
    stats = repo.get_stats()
    return stats

@app.get("/logs/recent")
def get_recent_logs(lines: int = 100, user: dict = Depends(get_current_user)):
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
def get_config_raw(user: dict = Depends(get_current_user)):
    config_path = os.environ.get("FILEFLOW_JOBS_CONFIG", "configs/jobs.yaml")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="Config file not found")
    with open(config_path, "r") as f:
        return {"content": f.read()}

@app.get("/api/scripts/{job_id}")
def get_script(job_id: str, user: dict = Depends(get_current_user)):
    """Return the inline bash script content for a job (if any)."""
    script_path = Path("configs/scripts") / f"{job_id}.sh"
    if not script_path.exists():
        return {"content": "", "path": ""}
    try:
        return {"content": script_path.read_text(), "path": str(script_path.resolve())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read script: {e}")


# ── Write endpoints (admin only) ──────────────────────────────────────────────

@app.post("/api/config")
async def save_config_raw(request: Request, user: dict = Depends(require_admin)):
    data = await request.json()
    content = data.get("content")
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Missing or empty 'content'")

    config_path = os.environ.get("FILEFLOW_JOBS_CONFIG", "configs/jobs.yaml")
    backup_path = config_path + ".bak"

    # Step 1: Validate YAML syntax
    try:
        parsed = yaml.safe_load(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML syntax: {str(e)}")

    # Step 2: Validate that jobs is a non-empty list
    jobs_list = parsed.get("jobs") if isinstance(parsed, dict) else None
    if not jobs_list or not isinstance(jobs_list, list) or len(jobs_list) == 0:
        raise HTTPException(
            status_code=400,
            detail="Configuration must contain at least one job under the 'jobs' key. Save aborted to protect existing config."
        )

    # Step 3: Backup current config before overwriting
    try:
        if os.path.exists(config_path):
            shutil.copy2(config_path, backup_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create backup before save: {str(e)}")

    # Step 4: Write new config
    try:
        with open(config_path, "w") as f:
            f.write(content)
    except Exception as e:
        try:
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, config_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to write config file: {str(e)}")

    # Step 5: Reload scheduler
    if _scheduler:
        try:
            new_config = load_jobs_config(config_path)
            _scheduler.clear_jobs()
            _scheduler.load_jobs_from_config(new_config)
        except Exception as e:
            try:
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, config_path)
            except Exception:
                pass
            raise HTTPException(
                status_code=400,
                detail=f"Config saved but failed scheduler validation — reverted to previous config: {str(e)}"
            )

    return {"status": "success", "message": f"Configuration saved ({len(jobs_list)} job(s)) and applied successfully"}


@app.post("/api/scripts/{job_id}")
async def save_script(job_id: str, request: Request, user: dict = Depends(require_admin)):
    """Save pasted bash script content for a job. Returns the absolute path."""
    data = await request.json()
    content = data.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Script content is empty")

    scripts_dir = Path("configs/scripts")
    scripts_dir.mkdir(parents=True, exist_ok=True)

    script_path = scripts_dir / f"{job_id}.sh"
    try:
        script_path.write_text(content)
        current = script_path.stat().st_mode
        script_path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save script: {e}")

    return {"status": "saved", "path": str(script_path.resolve())}


# ── Static / Dashboard (public) ───────────────────────────────────────────────

@app.get("/")
def serve_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
