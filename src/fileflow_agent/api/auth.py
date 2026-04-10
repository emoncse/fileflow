"""
Simple HMAC-signed token auth — no extra dependencies required.

Token format:  base64(username:role:issued_at) . hex_hmac_sha256_signature

Roles:
  admin  — full read/write access
  viewer — read-only access
"""
import os
import time
import hmac
import hashlib
import base64
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ── Config from environment ────────────────────────────────────────────────────
SECRET_KEY   = os.environ.get("AUTH_SECRET_KEY", "fileflow-change-me-in-production")
TOKEN_TTL    = int(os.environ.get("AUTH_TOKEN_TTL_HOURS", "8")) * 3600  # seconds

ADMIN_USERNAME  = os.environ.get("ADMIN_USERNAME",  "admin")
ADMIN_PASSWORD  = os.environ.get("ADMIN_PASSWORD",  "admin123")
VIEWER_USERNAME = os.environ.get("VIEWER_USERNAME", "viewer")
VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD", "viewer123")

USERS: dict[str, dict] = {
    ADMIN_USERNAME:  {"password": ADMIN_PASSWORD,  "role": "admin"},
    VIEWER_USERNAME: {"password": VIEWER_PASSWORD, "role": "viewer"},
}

# ── Token creation & verification ─────────────────────────────────────────────

def _sign(payload_b64: str) -> str:
    return hmac.new(
        SECRET_KEY.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()


def create_token(username: str, role: str) -> str:
    payload = f"{username}:{role}:{int(time.time())}"
    payload_b64 = base64.b64encode(payload.encode()).decode()
    sig = _sign(payload_b64)
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> dict | None:
    """Return {username, role} if token is valid and not expired, else None."""
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected = _sign(payload_b64)
        if not hmac.compare_digest(sig, expected):
            return None
        payload = base64.b64decode(payload_b64).decode()
        username, role, ts = payload.split(":", 2)
        if int(time.time()) - int(ts) > TOKEN_TTL:
            return None
        return {"username": username, "role": role}
    except Exception:
        return None


# ── FastAPI dependencies ───────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = verify_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
