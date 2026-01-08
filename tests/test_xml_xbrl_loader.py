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

def create_dummy_file(filename, content):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return os.path.abspath(filename)

def main():
    # Define test cases
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<note>
  <to>Tove</to>
  <from>Jani</from>
  <heading>Reminder</heading>
  <body>Don't forget me this weekend!</body>
</note>
"""
    xbrl_content = """<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance">
  <context id="c1">
    <entity>
      <identifier scheme="http://www.sec.gov/CIK">0000000000</identifier>
    </entity>
    <period>
      <instant>2024-12-31</instant>
    </period>
  </context>
  <unit id="u1">
    <measure>iso4217:USD</measure>
  </unit>
  <us-gaap:Assets decimals="-6" contextRef="c1" unitRef="u1">1000000</us-gaap:Assets>
</xbrl>
"""

    files_to_test = [
        ("test_document.xml", xml_content, "Don't forget me"),
        ("test_report.xbrl", xbrl_content, "us-gaap:Assets")
    ]
    
    created_files = []

    try:
        # Initialize BaseLoader to use local source
        loader = BaseLoader(source="local")

        for filename, content, expected_substring in files_to_test:
            abs_path = create_dummy_file(filename, content)
            created_files.append(abs_path)

            print(f"\n--- Testing with file: {filename} ---")
            
            # Call get_text method
            result = loader.get_text(input_list=[abs_path])
            
            text = result.get("text", "")
            print(f"Successfully extracted text ({len(text)} characters)")
            print(f"DEBUG: start {repr(text[:20])} end {repr(text[-20:])}")
            
            # Verify RAW content (no markdown wrapping)
            if not text.startswith("```"):
                 print(f"SUCCESS: Output is RAW content for {filename}.")
            else:
                 print(f"WARNING: Output wrapped in Markdown block for {filename} (Unexpected).")

            if expected_substring in text:
                print(f"SUCCESS: Text content verified for {filename}.")
            else:
                print(f"FAILURE: Expected content '{expected_substring}' not found in {filename}.")

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")
    finally:
        for fpath in created_files:
            if os.path.exists(fpath):
                os.remove(fpath)

if __name__ == "__main__":
    main()
