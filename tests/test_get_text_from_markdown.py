import os
import sys
from google.cloud import storage
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

# from polytext.loader import MarkdownLoader
from polytext.loader import BaseLoader

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize GCS client
    gcs_client = storage.Client()

    markdown_output = True
    source = "cloud"

    # Initialize MarkdownLoader with GCS client and bucket
    # markdown_loader = MarkdownLoader(
    #     gcs_client=gcs_client,
    #     document_gcs_bucket=os.getenv("GCS_BUCKET"),
    #     # llm_api_key=os.getenv("GOOGLE_API_KEY"),
    #     source=source,
    #     markdown_output=markdown_output
    # )

    markdown_loader = BaseLoader(
        # llm_api_key=os.getenv("GOOGLE_API_KEY"),
        source=source,
        markdown_output=markdown_output
    )

    # Define document data
    # file_path = "user_activity/user_id=1087/transcript.md"
    file_path = "gcs://opit-da-test-ml-ai-store-bucket/user_activity/user_id=1087/transcript.md"

    # file_path = "/Users/marcodelgiudice/Projects/polytext/transcript.md"

    try:
        # Call get_text_from_markdown method
        # document_text = markdown_loader.get_text_from_markdown(
        #     file_path=file_path,
        # )
        document_text = markdown_loader.get_text(
            input_list=[file_path],
        )

        import ipdb; ipdb.set_trace()

        try:
            output_file = "markdown_text.md" if markdown_output else "markdown_text.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(document_text["text"])
            print(f"Markdown text saved to {output_file}")
        except IOError as e:
            logging.error(f"Failed to save markdown text: {str(e)}")

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")


if __name__ == "__main__":
    main()