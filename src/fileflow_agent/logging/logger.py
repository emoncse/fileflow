import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from fileflow_agent.config.settings import load_settings

def get_logger(name: str) -> logging.Logger:
    settings = load_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if get_logger is called multiple times for the same name
    if logger.hasHandlers():
        return logger

    logger.setLevel(log_level)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    import os
    ws = Path(os.environ.get("FILEFLOW_WORKSPACE", "."))
    log_dir = ws / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        filename=log_dir / "fileflow.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
