import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from polytext.loader import BaseLoader

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_notebook_loader():
    test_file = os.path.abspath(os.path.join(os.path.dirname(__file__), 'temp', 'sample_long.ipynb'))
    
    print(f"Testing with file: {test_file}")
    
    # Test : Load with outputs
    loader = BaseLoader(source="local")
    result = loader.get_text(input_list=[test_file])
    
    print("\n--- Result with outputs ---")
    print(result['text'])

    print("\nTests passed successfully!")

if __name__ == "__main__":
    test_notebook_loader()
