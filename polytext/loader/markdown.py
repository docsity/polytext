# markdown.py
# Standard library imports
import os
import tempfile
import logging

# Local imports
from ..converter import md_to_text
from ..loader.downloader.downloader import Downloader

logger = logging.getLogger(__name__)


class MarkdownLoader:

    def __init__(self, source, markdown_output=True, s3_client=None, document_aws_bucket=None, gcs_client=None,
                 document_gcs_bucket=None, temp_dir="temp"):
        """
        Initialize the MarkdownLoader with cloud storage configurations.

        Handles markdown file loading and storage operations across AWS S3 and Google Cloud Storage.
        Sets up temporary directory for processing files.

        Args:
            source (str): Source of the markdown file. Must be either "cloud" or "local".
            markdown_output (bool, optional): If True, preserves markdown formatting. If False,
                converts to plain text. Defaults to True.
            s3_client (boto3.client, optional): AWS S3 client for S3 operations. Defaults to None.
            document_aws_bucket (str, optional): S3 bucket name for document storage. Defaults to None.
            gcs_client (google.cloud.storage.Client, optional): GCS client for Cloud Storage operations.
                Defaults to None.
            document_gcs_bucket (str, optional): GCS bucket name for document storage. Defaults to None.
            temp_dir (str, optional): Path for temporary file storage. Defaults to "temp".

        Raises:
            ValueError: If cloud storage clients are provided without bucket names
            OSError: If temp directory creation fails
        """
        self.source = source
        self.markdown_output = markdown_output
        self.s3_client = s3_client
        self.document_aws_bucket = document_aws_bucket
        self.gcs_client = gcs_client
        self.document_gcs_bucket = document_gcs_bucket

        # Set up custom temp directory
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

    def download_markdown(self, file_path, temp_file_path):
        """
        Download a markdown file from S3 or GCS to a local temporary path.

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

    def get_text_from_file(self, file_path: str) -> str:
        """
        Read and return the text content of a markdown file.

        If markdown_output is False, converts the content to plain text
        by removing markdown formatting.

        Args:
            file_path (str): Path to the markdown file.

        Returns:
            str: The text content, either with markdown formatting preserved
                or converted to plain text.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If there is an error reading the file.
        """
        logger.info(f"Reading markdown from file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                markdown_content = file.read()

            if not self.markdown_output:
                logger.info(f"Markdown output disabled. Markdown content will be converted to plain text.")
                markdown_content = md_to_text(markdown_content)

            return markdown_content

        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except IOError as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise

    def get_text_from_markdown(self, file_path):
        """
        Extract text from a markdown file from either cloud storage or local path.

        This method handles loading the markdown file from either a cloud storage
        service (S3 or GCS) or a local path, and then extracts its content while
        optionally preserving or removing markdown formatting.

        Args:
            file_path (str): Path to the markdown file. Can be a cloud storage path
                or a local file path.

        Returns:
            dict: A dictionary containing:
                - text (str): The extracted text content
                - completion_tokens (int): Always 0 for markdown files
                - prompt_tokens (int): Always 0 for markdown files
                - completion_model (str): Always "not provided" for markdown files
                - completion_model_provider (str): Always "not provided" for markdown files

        Raises:
            ValueError: If the source is not "cloud" or "local"
            FileNotFoundError: If the file does not exist
            IOError: If there is an error reading the file
        """
        logger.info("Starting text extraction from markdown...")

        # Load or download the document file
        if self.source == "cloud":
            fd, temp_file_path = tempfile.mkstemp()
            try:
                self.download_markdown(file_path, temp_file_path)
                logger.info(f"Successfully loaded markdown from {file_path}")
                text_from_markdown = self.get_text_from_file(temp_file_path)
            finally:
                os.close(fd)  # Close the file descriptor
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    logger.info(f"Removed temporary file {temp_file_path}")
        elif self.source == "local":
            text_from_markdown = self.get_text_from_file(file_path)
            logger.info(f"Successfully loaded markdown from local path {file_path}")
        else:
            raise ValueError("Invalid markdown source. Choose 'cloud' or 'local'.")

        return {
            "text": text_from_markdown,
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "completion_model": "not provided",
            "completion_model_provider": "not provided"
        }


