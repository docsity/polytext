import os
import sys
from google.cloud import storage
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.loader import VideoLoader

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize GCS client
    gcs_client = storage.Client()

    # Initialize VideoLoader with GCS client and bucket
    video_loader = VideoLoader(
        gcs_client=gcs_client,
        document_gcs_bucket='opit-da-test-ml-ai-store-bucket'
    )

    # Define document data
    file_path = "learning_resources/course_id=406/module_id=2658/id=31427/8434.mp4"

    local_file_path = "/Users/marcodelgiudice/Projects/polytext/tmpzcsjjw0g_video.mp4"

    # Optional: specify page range (start_page, end_page) - pages are 1-indexed
    page_range = (1, 1)  # Extract text from pages 1 to 10

    try:
        # Call get_document_text method
        document_text = video_loader.get_text_from_video(
            file_path=file_path,
            video_source="cloud",
        )

        # print(f"Successfully extracted text ({len(document_text)} characters)")
        # #print("Sample of extracted text:")
        # #print(document_text[:500] + "...")  # Print first 500 chars
        #
        # # Optionally save the extracted text to a file
        # with open("extracted_text.txt", "w", encoding="utf-8") as f:
        #     f.write(document_text)

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")


if __name__ == "__main__":
    main()