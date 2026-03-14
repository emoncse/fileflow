import os
import gzip
import shutil
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
    """Compresses a file using gzip."""
    out_path = f"{file_path}.gz"
    with open(file_path, 'rb') as f_in:
        with gzip.open(out_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return out_path

def decompress_step(file_path: str, context: Dict[str, Any]) -> str:
    """Decompresses a gzip file."""
    if not file_path.endswith('.gz'):
        logger.warning(f"File {file_path} does not end with .gz, skipping decompression")
        return file_path
    out_path = file_path[:-3]
    with gzip.open(file_path, 'rb') as f_in:
        with open(out_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return out_path

def rename_step(file_path: str, context: Dict[str, Any]) -> str:
    """Appends a timestamp or prefix based on context."""
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    prefix = context.get('rename_prefix', 'processed_')
    out_path = os.path.join(directory, f"{prefix}{filename}")
    os.rename(file_path, out_path)
    return out_path

class ProcessingPipeline:
    def __init__(self):
        self.registry: Dict[str, ProcessingStep] = {}
        self._register_default_steps()

    def _register_default_steps(self):
        self.register_step("compress", compress_step)
        self.register_step("decompress", decompress_step)
        self.register_step("rename", rename_step)

    def register_step(self, name: str, func: Callable[[str, Dict[str, Any]], str]):
        self.registry[name] = ProcessingStep(name, func)

    def execute_pipeline(self, steps: List[str], file_path: str, context: Dict[str, Any] = None) -> str:
        """Runs the file through a list of registered processing steps."""
        if not steps:
            return file_path
            
        context = context or {}
        current_path = file_path
        
        for step_name in steps:
            if step_name not in self.registry:
                raise ValueError(f"Unknown processing step: {step_name}")
            
            step = self.registry[step_name]
            current_path = step.execute(current_path, context)
            
        return current_path
