# video.py
# Standard library imports
import os
import re
import tempfile
import ffmpeg
import logging
from collections import Counter

# Local imports
from ..converter.audio_to_text import transcribe_audio
from ..loader.downloader.downloader import Downloader
from ..prompts.transcription import AUDIO_TO_MARKDOWN_PROMPT, AUDIO_TO_PLAIN_TEXT_PROMPT

logger = logging.getLogger(__name__)

class AudioLoader:

    def __init__(self, s3_client=None, document_aws_bucket=None, gcs_client=None, document_gcs_bucket=None):
        """
        Initialize AudioLoader with optional S3 or GCS configuration.

        Args:
            s3_client: Boto3 S3 client instance for AWS operations (optional)
            document_aws_bucket (str): Default S3 bucket name for document storage (optional)
        """
        self.s3_client = s3_client
        self.document_aws_bucket = document_aws_bucket
        self.gcs_client = gcs_client
        self.document_gcs_bucket = document_gcs_bucket

    def download_audio(self, file_path, temp_file_path):
        """
        Download an audio file from S3 or GCS to a local temporary path.

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

    def get_text_from_audio(self, file_path, audio_source, markdown_output=True):

        # Load or download the video file
        if audio_source == "cloud":
            fd, temp_file_path = tempfile.mkstemp()
            try:
                temp_file_path = self.download_audio(file_path, temp_file_path)
                logger.info(f"Successfully loaded audio file from {file_path}")
                # saved_video_path = self.save_file_locally(temp_file_path, os.getcwd(), 'video')
            finally:
                os.close(fd)  # Close the file descriptor
        elif audio_source == "local":
            temp_file_path = file_path
            logger.info(f"Successfully loaded audio file from local path {file_path}")
        else:
            raise ValueError("Invalid audio source. Choose 'cloud', or 'local'.")

        return transcribe_audio(audio_file=temp_file_path,
                                markdown_output=markdown_output
                                )
