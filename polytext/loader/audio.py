# video.py
# Standard library imports
import os
import tempfile
import logging

# Local imports
from ..converter.audio_to_text import transcribe_full_audio
from ..loader.downloader.downloader import Downloader

logger = logging.getLogger(__name__)

class AudioLoader:

    def __init__(
            self,
            source: str,
            s3_client: object = None,
            document_aws_bucket: str = None,
            gcs_client: object = None,
            document_gcs_bucket: str = None,
            llm_api_key: str = None,
            save_transcript_chunks: bool = False,
            temp_dir: str = 'temp',
            markdown_output: bool = True,
            bitrate_quality: int = 9,
            **kwargs
    ):
        """
        Initialize the AudioLoader with cloud storage and LLM configurations.

        Handles audio file loading and storage operations across AWS S3 and Google Cloud Storage.
        Sets up temporary directory for processing files.

        Args:
            source (str): Source of the audio file. Must be either "cloud" or "local".
            markdown_output (bool, optional): If True, the transcription will be formatted as Markdown. Defaults to True.
            s3_client (boto3.client, optional): AWS S3 client for S3 operations. Defaults to None.
            document_aws_bucket (str, optional): S3 bucket name for document storage. Defaults to None.
            gcs_client (google.cloud.storage.Client, optional): GCS client for Cloud Storage operations.
                Defaults to None.
            document_gcs_bucket (str, optional): GCS bucket name for document storage. Defaults to None.
            llm_api_key (str, optional): API key for language model service. Defaults to None.
            save_transcript_chunks (bool, optional): Whether to save chunk transcripts in final output. Defaults to False.
            temp_dir (str, optional): Path for temporary file storage. Defaults to "temp"
            bitrate_quality (int, optional): Variable bitrate quality from 0-9 (9 being lowest). Defaults to 9.

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
        self.llm_api_key = llm_api_key
        self.save_transcript_chunks = save_transcript_chunks
        self.type = "audio"
        self.bitrate_quality = bitrate_quality

        self.temp_dir = temp_dir

    def download_audio(self, file_path: str, temp_file_path: str) -> str:
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
        raise AttributeError('Storage client not provided')

    def get_text_from_audio(self, file_path: str) -> dict:
        """
        Extract text from an audio file by transcribing it.

        This method handles loading the audio file from either a cloud storage
        service (S3 or GCS) or a local path, and then transcribes the audio
        content into text using the `transcribe_audio` function.

        Args:
            file_path (str): Path to the audio file. This can be a cloud storage path or a local file path.

        Returns:
            str: The transcribed text from the audio file.

        Raises:
            ValueError: If the `audio_source` is not "cloud" or "local".
        """

        logger.info("Starting text extraction from audio...")

        # Load or download the video file
        if self.source == "cloud":
            # Create a temporary file inside the managed temp_dir
            temp_file_path = os.path.join(self.temp_dir, os.path.basename(file_path))
            self.download_audio(file_path, temp_file_path)
            logger.info(f"Successfully loaded audio file from {file_path}")
        elif self.source == "local":
            temp_file_path = file_path
            logger.info(f"Successfully loaded audio file from local path {file_path}")
        else:
            raise ValueError("Invalid audio source. Choose 'cloud', or 'local'.")

        result_dict = transcribe_full_audio(audio_file=temp_file_path,
                                                 markdown_output=self.markdown_output,
                                                 llm_api_key=self.llm_api_key,
                                                 save_transcript_chunks=self.save_transcript_chunks,
                                                 bitrate_quality=self.bitrate_quality
                                                 )

        result_dict["type"] = self.type
        result_dict["input"] = file_path

        return result_dict

    def load(self, input_path: str) -> dict:
        """
        Extract text from an audio file.

        Args:
            input_path (str): The audio file paths or URL.

        Returns:
            dict: A dictionary containing the transcribed text and related metadata.
        """
        return self.get_text_from_audio(file_path=input_path)