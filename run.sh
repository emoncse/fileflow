#!/bin/bash

# Navigate to the project directory
cd "$(dirname "$0")"

echo "Checking virtual environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

PYTHON_BIN="venv/bin/python3"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="venv/bin/python"
fi

if [ ! -f "$PYTHON_BIN" ]; then
    echo "Error: Failed to find python executable in venv/bin/"
    exit 1
fi

echo "Installing dependencies..."
"$PYTHON_BIN" -m pip install -r requirements.txt
"$PYTHON_BIN" -m pip install -e .

echo "----------------------------------------"
echo "Starting FileFlow Agent on port 7345..."
echo "Dashboard: http://localhost:7345"
echo "----------------------------------------"

# Run the application
"$PYTHON_BIN" src/fileflow_agent/main.py --port 7345
