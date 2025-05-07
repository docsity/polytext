# video.py
# Standard library imports
import os
import re
import tempfile
import logging
from collections import Counter

# Third-party imports
from pypdf import PdfReader
import fitz  # PyMuPDF
from botocore.exceptions import ClientError

# Local imports
from ..converter.pdf import convert_to_pdf
from ..exceptions.base import EmptyDocument, ExceededMaxPages
from ..loader.downloader.downloader import Downloader

logger = logging.getLogger(__name__)

class VideoLoader:

    def __init__(self, s3_client=None, document_aws_bucket=None, gcs_client=None, document_gcs_bucket=None):
        """
        Initialize VideoLoader with optional S3 or GCS configuration.

        Args:
            s3_client: Boto3 S3 client instance for AWS operations (optional)
            document_aws_bucket (str): Default S3 bucket name for document storage (optional)
        """
        self.s3_client = s3_client
        self.document_aws_bucket = document_aws_bucket
        self.gcs_client = gcs_client
        self.document_gcs_bucket = document_gcs_bucket

    def load_video_from_local_file(self):
        pass

    def download_video(self, file_path, temp_file_path):
        """
        Download a video file from S3 or GCS to a local temporary path.

        Args:
            file_path (str): Path to file in S3 or GCS bucket
            temp_file_path (str): Local path to save the downloaded file

        Returns:
            str: Path to the downloaded file (may be converted to PDF)

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

    def convert_video_to_audio(self, file_path):
        """
        Convert a video file to audio format.

        Args:
            video_file (str): Path to the video file.

        Returns:
            str: Path to the converted audio file.
        """

        fd, temp_file_path = tempfile.mkstemp()
        try:
            temp_file_path = self.download_video(file_path, temp_file_path)
            logger.info(f"Successfully loaded video file from {file_path}")
            return temp_file_path
        finally:
            os.close(fd)  # Close the file descriptor

    # def get_text_from_audio(self, markdown_output=True):
    #
    #     if markdown_output:
    #         # Convert the text to markdown format
    #         prompt_template = audio_to_markdown_prompt
    #     else:
    #         # Convert the text to plain text format
    #         prompt_template = audio_to_plain_text_prompt
    #
    #     audio_loader = AudioLoader()
    #
    #     audio_loader.transcribe_audio(
    #         audio_file=audio_file,
    #         prompt_template=prompt_template,
    #         language=self.language,
    #         model=self.model
    #     )
    #
    # def get_text_from_video(self, video_source, markdown_output=True):
    #     """
    #     Extract text from a video file.
    #
    #     Args:
    #         video_file (str): Path to the video file.
    #         markdown_output (bool): Whether to convert the text to markdown format.
    #
    #     Returns:
    #         str: Extracted text from the video.
    #     """
    #
    #     if video_source == "s3":
    #         # Download the video file from S3
    #         video = self.download_file_from_s3()
    #     elif video_source == "gcs":
    #         # Download the video file from GCS
    #         video = self.download_file_from_gcs()
    #     elif video_source == "local":
    #         # Load the video file from local storage
    #         video = self.load_video_from_local_file()
    #     else:
    #         raise ValueError("Invalid video source. Choose 's3', 'gcs', or 'local'.")
    #
    #     # Convert the video to audio
    #     audio = self.convert_video_to_audio()
    #
    #     # Get text from audio
    #     return self.get_text_from_audio(markdown_output)