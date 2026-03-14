import os
from fileflow_agent.config.settings import load_settings, load_jobs_config

def test_config():
    print("Testing AppSettings...")
    os.environ["SFTP_HOST"] = "test.sftp.com"
    settings = load_settings()
    print(f"SFTP Host: {settings.sftp_host}")
    print(f"Log Level: {settings.log_level}")
    print(f"SQL DB Path: {settings.sqlite_db_path}")

    print("\nTesting JobConfig...")
    # create dummy config
    dummy_yaml = """
jobs:
  - job_id: test_job_1
    enabled: true
    schedule: "0 * * * *"
    source:
      type: local
      path: /tmp/source
    destination:
      type: s3
      path: dest/
      bucket: my-bucket
    """
    with open("configs/test_jobs.yaml", "w") as f:
        f.write(dummy_yaml)
    
    jobs_config = load_jobs_config("configs/test_jobs.yaml")
    for job in jobs_config.jobs:
        print(f"Loaded Job: {job.job_id}, Enabled: {job.enabled}")
        print(f"  Source: {job.source.type} -> {job.source.path}")
        print(f"  Dest: {job.destination.type} -> {job.destination.bucket}/{job.destination.path}")

if __name__ == "__main__":
    test_config()
