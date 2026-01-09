import os
import sys
import logging
from unittest.mock import MagicMock

# Mock weasyprint dependencies to avoid environment errors during testing
sys.modules["weasyprint"] = MagicMock()
sys.modules["weasyprint.text"] = MagicMock()
sys.modules["weasyprint.text.ffi"] = MagicMock()
sys.modules["weasyprint.text.fonts"] = MagicMock()
sys.modules["weasyprint.css"] = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from polytext.loader.base import BaseLoader

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    # Define test cases with existing files
    files_to_test = [
        ("testxmlfile.xml", "Risposta"),
        ("Testxbrlfile.xbrl", "xbrl")
    ]
    
    current_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        # Initialize BaseLoader to use local source
        loader = BaseLoader(source="local")

        for filename, expected_substring in files_to_test:
            abs_path = os.path.join(current_dir, filename)

            if not os.path.exists(abs_path):
                print(f"Skipping {filename}: File not found at {abs_path}")
                continue

            print(f"\n--- Testing with file: {filename} ---")
            
            # Call get_text method
            result = loader.get_text(input_list=[abs_path])
            
            text = result.get("text", "")
            print(f"Successfully extracted text ({len(text)} characters)")
            print("-" * 50)
            print(f"PREVIEW START:\n{text[:500]}")
            print("-" * 50)
            print(f"DEBUG: Start: {repr(text[:20])}")
            print(f"DEBUG: End: {repr(text[-20:])}")

            # Verify RAW content wraps in Markdown
            if text.strip().startswith("```xml") and text.strip().endswith("```"):
                 print(f"SUCCESS: Output is correctly wrapped in Markdown code block for {filename}.")
            else:
                 print(f"FAILURE: Output is NOT wrapped in Markdown block for {filename} (Expected).")

            if expected_substring in text:
                print(f"SUCCESS: Text content verified for {filename}.")
            else:
                print(f"FAILURE: Expected content '{expected_substring}' not found in {filename}.")

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")

if __name__ == "__main__":
    main()
