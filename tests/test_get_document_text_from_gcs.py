import os
import sys
from google.cloud import storage
import logging
import boto3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.loader.base import BaseLoader
from polytext.exceptions.base import EmptyDocument

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize GCS client
    # gcs_client = storage.Client()
    # s3_client = boto3.client('s3')

    # Optional: specify page range (start_page, end_page) - pages are 1-indexed
    page_range = None # (1,2)  # Extract text from pages 1 to 10
    source = "cloud"
    markdown_output = True
    fallback_ocr = False

    # Initialize DocumentLoader with GCS client and bucket
    text_loader = BaseLoader(
        # gcs_client=None,
        # s3_client=s3_client,
        source=source,
        markdown_output=markdown_output,
        fallback_ocr=fallback_ocr,
        # document_gcs_bucket=None, #os.getenv("GCS_BUCKET"),
        # document_aws_bucket=os.environ.get("AWS_BUCKET"),
        page_range=page_range  # Optional
    )

    # Define document data
    # file_path = "gcs://opit-da-test-ml-ai-store-bucket/learning_resources/course_id=353/module_id=3056/id=31617/Supervisory+Agreement+Form+-+MSc.pdf"
    file_path = "s3://docsity-data/documents/original/2025/02/01/iiakfmyied-756df65b-2b69-46e2-8916-ce8d394829de-8087.odt"
    file_path = "s3://docsity-data/documents/original/2025/05/25/arb45ujrrv-4d6ef3d3-e4c4-4f3d-95b3-01d476c81ab3-9198.doc"
    # file_path = "s3://docsity-data/documents/original/2025/05/25/mzatlcs8ja-5ccf33be-9fd5-4b77-933b-67f95fb73ca3-4858.pdf"
    # file_path = "s3://docsity-ai/documents/uploads/2025/06/07/mbme4vnj-fa0a1418910209fb3cfb802fac25539913b2bae9.pdf"
    # file_path = "s3://docsity-ai/documents/uploads/2025/06/05/mbixox3p-65ffea88dad50a6ed0ca428a38ebe77ca651b0ed.pdf"
    local_file_path = "/Users/marcodelgiudice/Projects/polytext/prova_formato.pdf"

    try:
        # Call get_document_text method
        result_dict = text_loader.get_text(
            input_list=[file_path],
        )

        import ipdb; ipdb.set_trace()

        print(f"Successfully extracted text ({len(result_dict['text'])} characters)")
        #print("Sample of extracted text:")
        #print(document_text[:500] + "...")  # Print first 500 chars

        # Optionally save the extracted text to a file
        with open("md_4_doc.md", "w", encoding="utf-8") as f:
            f.write(result_dict['text'])

    except EmptyDocument as e:
        logging.error(f"Empty document error: {str(e)}")

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")


if __name__ == "__main__":
    main()