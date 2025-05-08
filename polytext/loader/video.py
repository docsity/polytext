# video.py
# Standard library imports
import os
import re
import tempfile
import ffmpeg
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

    # @staticmethod
    # def convert_video_to_audio_ffmpeg(video_file):
    #     """
    #     Convert a video file to audio format using FFmpeg.
    #
    #     Args:
    #         video_file (str): Path to the video file.
    #
    #     Returns:
    #         str: Path to the converted audio file.
    #
    #     Raises:
    #         subprocess.CalledProcessError: If FFmpeg conversion fails
    #     """
    #
    #     try:
    #         # Create temporary file for audio output
    #         fd, temp_audio_path = tempfile.mkstemp(suffix='.mp3')
    #         os.close(fd)
    #
    #         # FFmpeg command to extract audio
    #         # -y: Overwrite output file without asking
    #         # -i: Input file
    #         # -vn: Disable video
    #         # -acodec: Audio codec to use
    #         # -ab: Audio bitrate
    #         cmd = [
    #             'ffmpeg', '-y',
    #             '-i', video_file,
    #             '-vn',
    #             '-acodec', 'libmp3lame',
    #             '-ab', '192k',
    #             temp_audio_path
    #         ]
    #
    #         # Run FFmpeg command
    #         subprocess.run(cmd, check=True, capture_output=True)
    #
    #         logger.info(f"Successfully converted video to audio: {temp_audio_path}")
    #         return temp_audio_path

    @staticmethod
    def convert_video_to_audio(video_file):
        """
        Convert a video file to audio format using ffmpeg-python.

        Args:
            video_file (str): Path to the video file.

        Returns:
            str: Path to the converted audio file.

        Raises:
            ffmpeg.Error: If FFmpeg conversion fails
            Exception: If any other error occurs during conversion
        """
        temp_audio_path = None
        try:
            # Create temporary file for audio output
            fd, temp_audio_path = tempfile.mkstemp(suffix='.mp3')
            os.close(fd)

            # Simple efficient pipeline
            (
                ffmpeg
                .input(video_file)
                .output(temp_audio_path, acodec='libmp3lame', ab='192k', vn=None)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            logger.info(f"Successfully converted video to audio: {temp_audio_path}")
            return temp_audio_path

        except ffmpeg.Error as e:
            logger.error(f"FFmpeg conversion failed: {e.stderr.decode()}")
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
            raise
        except Exception as e:
            logger.error(f"Failed to convert video to audio: {str(e)}")
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
            raise

    def get_text_from_video(self, file_path, video_source, markdown_output=True):
        """
        Extract text from a video file.

        Args:
            file_path (str): Path to the video file.
            video_source (str): Source of the video ('cloud' or 'local').
            markdown_output (bool): Whether to convert the text to markdown format. Defaults to True.

        Returns:
            str: Extracted text from the video.
        """

        # Load or download the video file
        if video_source == "cloud":
            fd, temp_file_path = tempfile.mkstemp()
            try:
                temp_file_path = self.download_video(file_path, temp_file_path)
                logger.info(f"Successfully loaded video file from {file_path}")
                # saved_video_path = self.save_file_locally(temp_file_path, os.getcwd(), 'video')
            finally:
                os.close(fd)  # Close the file descriptor
        elif video_source == "local":
            temp_file_path = file_path
            logger.info(f"Successfully loaded video file from local path {file_path}")
        else:
            raise ValueError("Invalid video source. Choose 'cloud', or 'local'.")

        # Convert the video to audio
        audio_path = self.convert_video_to_audio(temp_file_path)
        # saved_audio_path = self.save_file_locally(audio_path, os.getcwd(), 'audio')

        # Get text from audio
        return "ok" # self.get_text_from_audio(audio_path)

    def get_text_from_audio(self, audio_path, markdown_output=True):

        if markdown_output:
            # Convert the text to markdown format
            prompt_template = audio_to_markdown_prompt
        else:
            # Convert the text to plain text format
            prompt_template = audio_to_plain_text_prompt

        audio_loader = AudioLoader()

        audio_loader.transcribe_audio(
            audio_file=audio_file,
            prompt_template=prompt_template,
            language=self.language,
            model=self.model
        )

    # @staticmethod
    # def save_file_locally(source_path, destination_dir, file_type):
    #     """
    #     Save a file to a local directory with proper naming.
    #
    #     Args:
    #         source_path (str): Path to the source file
    #         destination_dir (str): Directory to save the file
    #         file_type (str): Type of file ('video' or 'audio')
    #
    #     Returns:
    #         str: Path to the saved file
    #     """
    #     from pathlib import Path
    #     # Create directory if it doesn't exist
    #     os.makedirs(destination_dir, exist_ok=True)
    #
    #     # Extract original filename from path
    #     original_filename = Path(source_path).name
    #     base_name = os.path.splitext(original_filename)[0]
    #
    #     # Create new filename
    #     extension = '.mp4' if file_type == 'video' else '.mp3'
    #     new_filename = f"{base_name}_{file_type}{extension}"
    #
    #     # Create full destination path
    #     destination_path = os.path.join(destination_dir, new_filename)
    #
    #     # Copy the file
    #     with open(source_path, 'rb') as src, open(destination_path, 'wb') as dst:
    #         dst.write(src.read())
    #
    #     logger.info(f"Saved {file_type} file to: {destination_path}")
    #     return destination_path

