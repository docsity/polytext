# ocr.py
# Standard library imports
import os
import tempfile
import logging

# Local imports
from ..converter.audio_to_text import transcribe_full_audio # TODO: Update import to OCR module
from ..loader.downloader.downloader import Downloader

logger = logging.getLogger(__name__)


class OCRLoader:

    def __init__(self, s3_client=None, document_aws_bucket=None, gcs_client=None, document_gcs_bucket=None,
                 llm_api_key=None, temp_dir="temp"):
        """
        Initialize the OCRLoader with cloud storage and LLM configurations.

        Handles document loading and storage operations across AWS S3 and Google Cloud Storage.
        Sets up temporary directory for processing files.

        Args:
            s3_client (boto3.client, optional): AWS S3 client for S3 operations. Defaults to None.
            document_aws_bucket (str, optional): S3 bucket name for document storage. Defaults to None.
            gcs_client (google.cloud.storage.Client, optional): GCS client for Cloud Storage operations.
                Defaults to None.
            document_gcs_bucket (str, optional): GCS bucket name for document storage. Defaults to None.
            llm_api_key (str, optional): API key for language model service. Defaults to None.
            temp_dir (str, optional): Path for temporary file storage. Defaults to "temp".

        Raises:
            ValueError: If cloud storage clients are provided without bucket names
            OSError: If temp directory creation fails
        """
        self.s3_client = s3_client
        self.document_aws_bucket = document_aws_bucket
        self.gcs_client = gcs_client
        self.document_gcs_bucket = document_gcs_bucket
        self.llm_api_key = llm_api_key

        # Set up custom temp directory
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

    def download_document(self, file_path, temp_file_path):
        """
        Download a document from S3 or GCS to a local temporary path.

        Args:
            file_path (str): Path to file in S3 or GCS bucket
            temp_file_path (str): Local path to save the downloaded file

        Returns:
            str: Path to the downloaded file

        Raises:
            ClientError: If download operation fails
        """
        if self.s3_client is not None:
            downloader = Downloader(s3_client=self.s3_client, document_aws_bucket=self.document_aws_bucket)
            downloader.download_file_from_s3(file_path, temp_file_path)
            logger.info(f'Downloaded {file_path} to {temp_file_path}')
            return temp_file_path
        elif self.gcs_client is not None:
            downloader = Downloader(gcs_client=self.gcs_client, document_gcs_bucket=self.document_gcs_bucket)
            downloader.download_file_from_gcs(file_path, temp_file_path)
            logger.info(f'Downloaded {file_path} to {temp_file_path}')
            return temp_file_path

    def get_text_from_ocr(self, image_paths, source, markdown_output=True):
        """
        Extract text from a document using OCR.

        This method handles loading the document from either a cloud storage
        service (S3 or GCS) or a local path, and then performs OCR to extract
        text content using the `get_full_ocr` function.

        Args:
            file_path (str): Path to the document. This can be a cloud storage path or a local file path.
            source (str): Source of the document. Must be either "cloud" or "local".
            markdown_output (bool, optional): If True, the extracted text will be formatted as Markdown.
                Defaults to True.

        Returns:
            str: The extracted text from the document.

        Raises:
            ValueError: If the `source` is not "cloud" or "local".
        """
        logger.info("Starting text extraction using OCR...")

        # Load or download the document file
        if source == "cloud":
            fd, temp_file_path = tempfile.mkstemp()
            try:
                temp_files = []
                for image_path in image_paths:
                    fd, temp_file = tempfile.mkstemp()
                    os.close(fd)
                    temp_file_path = self.download_document(image_path, temp_file)
                    temp_files.append(temp_file_path)
                    logger.info(f"Successfully loaded document from {image_path}")
            finally:
                os.close(fd)  # Close the file descriptor
        elif source == "local":
            temp_files = image_paths  # For local files, use the paths directly
            for image_path in image_paths:
                logger.info(f"Successfully loaded document from local path {image_path}")
        else:
            raise ValueError("Invalid OCR source. Choose 'cloud' or 'local'.")

        text_from_ocr = get_full_ocr(document_file=temp_files,
                                    markdown_output=markdown_output,
                                    llm_api_key=self.llm_api_key)

        # Clean up temporary file if it was downloaded
        if source == "cloud":
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"Removed temporary file {temp_file}")

        return text_from_ocr