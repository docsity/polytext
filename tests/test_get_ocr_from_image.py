import os
import sys
from google.cloud import storage
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.loader import AudioLoader
from polytext.converter.ocr_to_text import OCRToTextConverter

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize GCS client
    gcs_client = storage.Client()

    markdown_output = True

    # # Initialize VideoLoader with GCS client and bucket
    # audio_loader = AudioLoader(
    #     gcs_client=gcs_client,
    #     document_gcs_bucket='opit-da-test-ml-ai-store-bucket',
    #     # llm_api_key=os.getenv("GOOGLE_API_KEY"),
    #     save_transcript_chunks=save_transcript_chunks,
    # )

    # Initialize OCRToTextConverter
    ocr_to_text_converter = OCRToTextConverter()

    # Define document data
    file_path = ""

    local_file_path = "/Users/marcodelgiudice/Projects/polytext/IMG_9695.jpg"
    local_file_paths = ["/Users/marcodelgiudice/Projects/polytext/IMG_9695.jpg",
                        "/Users/marcodelgiudice/Projects/polytext/IMG_9701.jpg",
                        "/Users/marcodelgiudice/Projects/polytext/IMG_9702.jpg"]
    local_file_paths = ["/Users/marcodelgiudice/Projects/polytext/dickens.png"]

    try:
        # # Call get_document_text method
        # document_text = audio_loader.get_text_from_audio(
        #     file_path=local_file_path,
        #     audio_source="local",
        #     markdown_output=markdown_output
        # )

        # Call get_ocr method
        document_text = ocr_to_text_converter.get_ocr(
            files_for_ocr=local_file_paths,
        )

        import ipdb; ipdb.set_trace()

        try:
            output_file = "transcript.md" if markdown_output else "transcript.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(document_text["transcript"])
            print(f"Transcript saved to {output_file}")
        except IOError as e:
            logging.error(f"Failed to save transcript: {str(e)}")

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