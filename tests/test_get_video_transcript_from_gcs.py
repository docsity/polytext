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

    markdown_output = True
    save_transcript_chunks = True
    source = "local"
    bitrate_quality = 8

    # Initialize VideoLoader with GCS client and bucket
    video_loader = VideoLoader(
        source=source,
        markdown_output=markdown_output,
        bitrate_quality=bitrate_quality,
        gcs_client=gcs_client,
        document_gcs_bucket=os.getenv("GCS_BUCKET"),
        # llm_api_key=os.getenv("GOOGLE_API_KEY"),
        save_transcript_chunks=save_transcript_chunks,
    )

    # Define document data
    # file_path = "learning_resources/course_id=406/module_id=2658/id=31427/8434.mp4"
    # file_path = "learning_resources/course_id=132/module_id=312/id=4020/2333.mp4"

    file_path = "/Users/marcodelgiudice/Projects/polytext/tmpzcsjjw0g_video.mp4"

    try:
        # Call get_document_text method
        document_text = video_loader.get_text_from_video(
            file_path=file_path,
        )

        import ipdb; ipdb.set_trace()

        try:
            output_file = "transcript.md" if markdown_output else "transcript.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(document_text["text"])
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