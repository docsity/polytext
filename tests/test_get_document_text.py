import os
import sys
import boto3
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.loader import TextLoader

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize S3 client (optional, only needed if loading from S3)
    s3_client = boto3.client('s3')

    # Initialize TextLoader with S3 client and bucket
    text_loader = TextLoader(
        s3_client=s3_client,
        document_aws_bucket='docsity-data'
    )

    # Define document data
    doc_data = {
        "file_path": "documents/original/2025/02/01/iiakfmyied-756df65b-2b69-46e2-8916-ce8d394829de-8087.odt",
        # "bucket": "docsity-data"  # Optional if already set in TextLoader initialization
    }

    # Optional: specify page range (start_page, end_page) - pages are 1-indexed
    page_range = (61, 62)  # Extract text from pages 1 to 10

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