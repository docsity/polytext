import os
import sys
from google.cloud import storage
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.loader import OCRLoader
from polytext.converter.ocr_to_text import OCRToTextConverter

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize GCS client
    gcs_client = storage.Client()

    markdown_output = True

    # Initialize OCRLoader with GCS client and bucket
    ocr_loader = OCRLoader(
        gcs_client=None, #gcs_client,
        document_gcs_bucket=None, #'opit-da-test-ml-ai-store-bucket',
        # llm_api_key=os.getenv("GOOGLE_API_KEY"),
    )

    # Define document data
    file_path = ""

    local_file_path = "/Users/marcodelgiudice/Projects/polytext/IMG_9695.tiff"

    try:
        # Call get_text_from_ocr method
        document_text = ocr_loader.get_text_from_ocr(
            file_path=local_file_path,
            source="local",
            markdown_output=markdown_output
        )

        import ipdb; ipdb.set_trace()

        try:
            output_file = "transcript.md" if markdown_output else "transcript.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(document_text["text"])
            print(f"Transcript saved to {output_file}")
        except IOError as e:
            logging.error(f"Failed to save transcript: {str(e)}")

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")


if __name__ == "__main__":
    main()