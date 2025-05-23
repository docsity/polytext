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
    # Initialize GCS client
    gcs_client = storage.Client()

    markdown_output = True
    save_transcript_chunks = True

    # Initialize VideoLoader with GCS client and bucket
    loader = BaseLoader()

    # Define document data
    file_path = "learning_resources/course_id=406/module_id=2658/id=31427/8434.mp4"

    local_file_path = "/Users/andreasolfanelli/Projects/polytext/lunedì alle 17-21.aac"

    # Call get_document_text method
    result_dict = loader.get_text(
        input_list=[local_file_path],
        source="local",
        markdown_output=markdown_output
    )
    import ipdb; ipdb.set_trace()

    try:
        output_file = "transcript.md" if markdown_output else "transcript.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result_dict["text"])
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



if __name__ == "__main__":
    main()