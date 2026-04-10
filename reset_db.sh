#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# reset_db.sh — Drop the FileFlow tracking database and re-apply the schema.
#
# Usage:
#   ./reset_db.sh           (uses DB path from .env / default: data/tracking.db)
#   ./reset_db.sh --yes     (skip confirmation prompt)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Resolve DB path (honour .env if present) ──────────────────────────────────
ENV_FILE=".env"
DB_PATH="data/tracking.db"   # default

if [[ -f "$ENV_FILE" ]]; then
    # Extract SQLITE_DB_PATH=... from .env (ignore comments)
    _env_val=$(grep -E '^SQLITE_DB_PATH=' "$ENV_FILE" | tail -1 | cut -d'=' -f2- | tr -d '[:space:]')
    if [[ -n "$_env_val" ]]; then
        DB_PATH="$_env_val"
    fi
fi

echo ""
echo "  FileFlow Agent — Database Reset"
echo "  ───────────────────────────────"
echo "  DB path : $DB_PATH"
echo ""

# ── Confirmation ──────────────────────────────────────────────────────────────
if [[ "${1:-}" != "--yes" ]]; then
    read -r -p "  ⚠️  This will DELETE all transfer records. Continue? [y/N] " confirm
    echo ""
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "  Aborted."
        exit 0
    fi
fi

# ── Remove existing DB ────────────────────────────────────────────────────────
if [[ -f "$DB_PATH" ]]; then
    rm -f "$DB_PATH"
    echo "  ✓ Removed: $DB_PATH"
else
    echo "  (No existing database found at $DB_PATH)"
fi

# ── Re-run schema via Python (uses the same init_db() as the app) ─────────────
echo "  Running schema migration…"

PYTHON="./venv/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON="python3"
fi

"$PYTHON" - <<'PYEOF'
import sys, os
sys.path.insert(0, "src")
os.chdir(os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else ".")

from fileflow_agent.tracking.database import init_db
init_db()
print("  ✓ Schema applied — fresh database is ready.")
PYEOF

echo ""
echo "  Done. Start the agent with: ./run.sh"
echo ""
