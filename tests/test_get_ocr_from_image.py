import os
import sys
from google.cloud import storage
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.loader import BaseLoader

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    markdown_output = True
    target_size = 1
    source = "local"

    # Initialize OCRLoader with GCS client and bucket
    ocr_loader = BaseLoader(
        gcs_client=None, #gcs_client,
        document_gcs_bucket=None, #os.getenv("GCS_BUCKET"),
        # llm_api_key=os.getenv("GOOGLE_API_KEY"),
        target_size=target_size,
        source=source,
        markdown_output=markdown_output
    )

    # Define document data
    file_url = ""

    local_file_path = "/Users/marcodelgiudice/Projects/polytext/IMG_9695.tiff"

    try:
        # Call get_text method
        result_dict = ocr_loader.get_text(
            input_list=[local_file_path],
        )

        import ipdb; ipdb.set_trace()

        try:
            output_file = "transcript.md" if markdown_output else "transcript.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result_dict["text"])
            print(f"Transcript saved to {output_file}")
        except IOError as e:
            logging.error(f"Failed to save transcript: {str(e)}")

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")


if __name__ == "__main__":
    main()