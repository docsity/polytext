import os
import sys
from google.cloud import storage
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.loader import TextLoader

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize GCS client
    gcs_client = storage.Client()

    # Initialize TextLoader with GCS client and bucket
    text_loader = TextLoader(
        gcs_client=gcs_client,
        document_gcs_bucket='opit-da-test-ml-ai-store-bucket'
    )

    # Define document data
    doc_data = {
        "file_path": "learning_resources/course_id=353/module_id=3056/id=31617/Supervisory+Agreement+Form+-+MSc.pdf",
        # "bucket": "docsity-data"  # Optional if already set in TextLoader initialization
    }

    # Optional: specify page range (start_page, end_page) - pages are 1-indexed
    page_range = (1, 1)  # Extract text from pages 1 to 10

    try:
        # Call get_document_text method
        document_text = text_loader.get_document_text(
            doc_data=doc_data,
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