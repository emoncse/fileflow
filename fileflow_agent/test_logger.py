import os
import sys

# Add src to Python path so we can import fileflow_agent directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from fileflow_agent.logging.logger import get_logger

def test_logger():
    # Make sure logs dir exists
    import os
    os.makedirs("logs", exist_ok=True)
    
    logger = get_logger("test_logging")
    logger.info("This is an info message: job started")
    logger.warning("This is a warning message: file discovered")
    logger.error("This is an error message: checksum created")
    
    print("Logs written. Check console output and logs/fileflow.log")

if __name__ == "__main__":
    test_logger()
