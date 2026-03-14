import os
import sys

# Add src to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from fileflow_agent.processing.pipeline import ProcessingPipeline

def test_pipeline():
    pipeline = ProcessingPipeline()
    
    # Create dummy file
    test_file = "test_data.txt"
    with open(test_file, "w") as f:
        f.write("test data content for processing")
    
    print(f"Original file: {test_file}")
    
    # Test compress
    compressed = pipeline.execute_pipeline(["compress"], test_file)
    print(f"Compressed file: {compressed}")
    
    # Test rename
    renamed = pipeline.execute_pipeline(["rename"], compressed, {"rename_prefix": "archived_"})
    print(f"Renamed file: {renamed}")
    
    # Test decompress
    decompressed = pipeline.execute_pipeline(["decompress"], renamed)
    print(f"Decompressed file: {decompressed}")
    
    # Verify contents
    with open(decompressed, "r") as f:
        print(f"Content: {f.read()}")
        
    # Cleanup
    for f in [test_file, compressed, renamed, decompressed]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass

if __name__ == "__main__":
    test_pipeline()
