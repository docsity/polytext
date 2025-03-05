import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.loader import TextLoader

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize TextLoader
    text_loader = TextLoader()

    # Optional: specify page range (start_page, end_page) - pages are 1-indexed
    page_range = (1, 2)  # Extract text from pages 1 to 10

    try:
        # Call get_document_text method
        document_text = text_loader.extract_text_from_file(
            file_path="test_load.odt",
            page_range=page_range  # Optional
        )

        print(f"Successfully extracted text ({len(document_text)} characters)")
        #print("Sample of extracted text:")
        #print(document_text[:500] + "...")  # Print first 500 chars

        # Optionally save the extracted text to a file
        with open("extracted_text.txt", "w", encoding="utf-8") as f:
            f.write(document_text)

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")


if __name__ == "__main__":
    main()
