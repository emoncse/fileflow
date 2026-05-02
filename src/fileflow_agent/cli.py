import os
import sys
import argparse
import shutil
from pathlib import Path
from fileflow_agent.main import start_agent

def init_workspace(workspace_dir: str):
    base = Path(workspace_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    
    # Create required subdirectories
    for d in ["logs", "data", "configs/scripts", "backups"]:
        (base / d).mkdir(parents=True, exist_ok=True)
        
    # Create empty jobs file if it doesn't exist
    jobs_file = base / "configs" / "jobs.yaml"
    if not jobs_file.exists():
        jobs_file.write_text("jobs: []\n")
        
    # Create empty .env if it doesn't exist
    env_file = base / ".env"
    if not env_file.exists():
        env_file.write_text(
            "AUTH_SECRET_KEY=change-me-in-production-1234567890\n"
            "AUTH_TOKEN_TTL_HOURS=24\n"
            "ADMIN_USERNAME=admin\n"
            "ADMIN_PASSWORD=admin\n"
            "VIEWER_USERNAME=viewer\n"
            "VIEWER_PASSWORD=viewer\n"
        )
        
    print(f"✅ Initialized FileFlow Agent workspace at: {base}")
    print("Next steps:")
    print(f"  cd {base}")
    print(f"  fileflow start .")

def start_workspace(workspace_dir: str, host: str, port: int):
    base = Path(workspace_dir).resolve()
    if not base.exists() or not (base / "configs" / "jobs.yaml").exists():
        print(f"❌ Error: Workspace not found or invalid at {base}")
        print("Run 'fileflow init <dir>' first to initialize it.")
        sys.exit(1)
        
    # Set the workspace environment variable so all other modules use it
    os.environ["FILEFLOW_WORKSPACE"] = str(base)
    
    # Start the agent
    start_agent(host=host, port=port)

def main():
    parser = argparse.ArgumentParser(description="FileFlow Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    init_parser = subparsers.add_parser("init", help="Initialize a new fileflow workspace")
    init_parser.add_argument("directory", type=str, nargs="?", default=".", help="Directory to initialize")
    
    start_parser = subparsers.add_parser("start", help="Start the fileflow agent")
    start_parser.add_argument("directory", type=str, nargs="?", default=".", help="Workspace directory to start")
    start_parser.add_argument("--host", type=str, default="0.0.0.0", help="API host (default: 0.0.0.0)")
    start_parser.add_argument("--port", type=int, default=7345, help="API port (default: 7345)")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_workspace(args.directory)
    elif args.command == "start":
        start_workspace(args.directory, args.host, args.port)

if __name__ == "__main__":
    main()
