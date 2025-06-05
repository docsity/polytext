import logging
from polytext.loader import BaseLoader

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('polytext')

# Create loader instance
text_loader = BaseLoader(
        # gcs_client=None,
        # s3_client=s3_client,
        source="cloud",
        markdown_output=True,
        # document_gcs_bucket=None, #os.getenv("GCS_BUCKET"),
        # document_aws_bucket=os.environ.get("AWS_BUCKET"),
        page_range=(1,2)  # Optional
    )

# Test with your file
file_path = "s3://docsity-data/documents/original/2025/05/25/mzatlcs8ja-5ccf33be-9fd5-4b77-933b-67f95fb73ca3-4858.pdf"
logger.debug(f"Testing with file: {file_path}")

try:
    result_dict = text_loader.get_text(input_list=[file_path])
except Exception as e:
    logger.error(f"Error processing file: {str(e)}")
    logger.debug(f"Temp file location: {text_loader.temp_dir}")

import ipdb; ipdb.set_trace()