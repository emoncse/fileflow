import os
import bz2
import gzip
import shutil
import zipfile
import subprocess
from datetime import datetime
from typing import List, Callable, Dict, Any
from fileflow_agent.logging.logger import get_logger

logger = get_logger("fileflow_agent.processing.pipeline")

class ProcessingStep:
    def __init__(self, name: str, func: Callable[[str, Dict[str, Any]], str]):
        self.name = name
        self.func = func

    def execute(self, file_path: str, context: Dict[str, Any]) -> str:
        logger.info(f"Executing processing step: {self.name} on {file_path}")
        return self.func(file_path, context)

def compress_step(file_path: str, context: Dict[str, Any]) -> str:
    """Compresses a file using gzip (.gz)."""
    out_path = f"{file_path}.gz"
    with open(file_path, 'rb') as f_in:
        with gzip.open(out_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return out_path

def decompress_step(file_path: str, context: Dict[str, Any]) -> str:
    """Decompresses a gzip (.gz) file."""
    if not file_path.endswith('.gz'):
        logger.warning(f"File {file_path} does not end with .gz, skipping decompression")
        return file_path
    out_path = file_path[:-3]
    with gzip.open(file_path, 'rb') as f_in:
        with open(out_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return out_path

def zip_step(file_path: str, context: Dict[str, Any]) -> str:
    """Packages a file into a .zip archive."""
    out_path = f"{file_path}.zip"
    filename = os.path.basename(file_path)
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(file_path, filename)
    return out_path

def compress_bz2_step(file_path: str, context: Dict[str, Any]) -> str:
    """Compresses a file using bzip2 (.bz2)."""
    out_path = f"{file_path}.bz2"
    with open(file_path, 'rb') as f_in:
        with bz2.open(out_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return out_path

def rename_step(file_path: str, context: Dict[str, Any]) -> str:
    """Prepends a job-id prefix to the filename."""
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    prefix = context.get('rename_prefix', 'processed_')
    out_path = os.path.join(directory, f"{prefix}{filename}")
    os.rename(file_path, out_path)
    return out_path

def timestamp_step(file_path: str, context: Dict[str, Any]) -> str:
    """Prepends a YYYYMMDD_ date stamp to the filename."""
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    stamp = datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(directory, f"{stamp}_{filename}")
    os.rename(file_path, out_path)
    return out_path

class ProcessingPipeline:
    def __init__(self):
        self.registry: Dict[str, ProcessingStep] = {}
        self._register_default_steps()

    def _register_default_steps(self):
        self.register_step("compress", compress_step)
        self.register_step("decompress", decompress_step)
        self.register_step("zip", zip_step)
        self.register_step("compress_bz2", compress_bz2_step)
        self.register_step("rename", rename_step)
        self.register_step("timestamp", timestamp_step)

    def register_step(self, name: str, func: Callable[[str, Dict[str, Any]], str]):
        self.registry[name] = ProcessingStep(name, func)

    def execute_pipeline(self, steps: List[str], file_path: str, context: Dict[str, Any] = None) -> str:
        """Runs the file through a list of registered processing steps in order.

        Steps are either:
          - A registered step name (e.g. 'compress', 'rename')
          - A bash script step in the form 'bash_script:/absolute/path/to/script.sh'
            The script receives the file path as $1. If it prints a new file path to
            stdout, that path is used for subsequent steps; otherwise the original
            path is kept (script modified the file in-place).
        """
        if not steps:
            return file_path

        context = context or {}
        current_path = file_path

        for step_name in steps:
            if step_name.startswith('bash_script:'):
                script_path = step_name[len('bash_script:'):].strip()
                current_path = self._run_bash_script(current_path, script_path)
            elif step_name in self.registry:
                step = self.registry[step_name]
                current_path = step.execute(current_path, context)
            else:
                raise ValueError(f"Unknown processing step: '{step_name}'")

        return current_path

    def _run_bash_script(self, file_path: str, script_path: str) -> str:
        """Execute a user-supplied bash script against the file."""
        if not script_path:
            raise ValueError("bash_script step requires a non-empty script path")
        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"Script not found: {script_path}")

        logger.info(f"Executing custom bash script: {script_path} on {file_path}")

        try:
            result = subprocess.run(
                ['bash', script_path, file_path],
                capture_output=True,
                text=True,
                timeout=300,  # 5-minute hard limit per script
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Script '{script_path}' timed out after 300 seconds")
        except Exception as e:
            raise RuntimeError(f"Failed to launch script '{script_path}': {e}")

        if result.returncode != 0:
            stderr = result.stderr.strip() or "(no stderr)"
            raise RuntimeError(
                f"Script '{script_path}' exited with code {result.returncode}: {stderr}"
            )

        # If script printed a path to stdout and that path exists, use it as output.
        new_path = result.stdout.strip()
        if new_path and os.path.exists(new_path):
            logger.info(f"Script produced new file: {new_path}")
            return new_path

        # Otherwise assume the script modified the file in-place.
        return file_path
