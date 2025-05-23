# Standard library imports
import os
import tempfile
import logging

# External library imports
from youtube_transcript_api import YouTubeTranscriptApi
from xml.etree.ElementTree import ParseError
from requests.exceptions import ConnectionError
from retry import retry

# Local imports
from ..converter.text_to_md import text_to_md

logger = logging.getLogger(__name__)


class YoutubeTranscriptLoader:
    """
    Class to download, and process transcripts from YouTube videos.
    """

    def __init__(self, llm_api_key: str = None, save_transcript_chunks: bool = False, temp_dir: str = 'temp') -> None:
        """
        Initialize YoutubeTranscriptLoader class with API key and configuration.

        Args:
            llm_api_key (str, optional): API key for the LLM used for processing.
            save_transcript_chunks (bool, optional): Whether to include processed chunks in final output.
            temp_dir (str, optional): Temporary directory to store intermediate transcript files.
        """
        self.llm_api_key = llm_api_key
        self.save_transcript_chunks = save_transcript_chunks
        self.type = "youtube"

        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

        self.output_path = os.path.join(self.temp_dir, f"youtube_transcript.txt")

    @retry(
        (
                ParseError,
                ConnectionError,
        ),
        tries=8,
        delay=3,
        backoff=2,
        logger=logger,
    )
    def download_transcript_from_youtube(self, video_url: str, output_path: str) -> str:
        """
        Download the transcript of a YouTube video and save it as plain text.

        Args:
            video_url (str): The URL of the YouTube video.
            output_path (str): Local path to save the transcript file.

        Returns:
            str: Transcript text.

        Raises:
            Exception: If transcript is not found or any error occurs during download.
        """

        ytt_api = YouTubeTranscriptApi()

        # Get video id
        video_id = self.extract_video_id(video_url)

        # Get available transcripts
        transcripts = ytt_api.list(video_id)
        # Get the available languages of the transcript
        languages = [t.language_code for t in transcripts]

        logging.info("****Fetching transcript from YouTube****")
        transcript_data = ytt_api.fetch(video_id, languages)

        if not transcript_data:
            raise Exception("No subtitles found in the transcript")

        # Extract plain text
        plain_text = "\n".join(line.text for line in transcript_data)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f_out:
            f_out.write(plain_text)

        return plain_text

    @staticmethod
    def extract_video_id(url: str) -> str:
        """
        Extract the video ID from a YouTube URL.

        Args:
            url (str): YouTube video URL.

        Returns:
            str: Extracted video ID.

        Raises:
            ValueError: If the URL format is not valid.
        """
        if "watch?v=" in url:
            return url.split("watch?v=")[-1]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[-1]
        else:
            raise ValueError("Invalid YouTube URL format")

    def download_transcript(self, video_url: str) -> str:
        """
        Download and return the transcript from a YouTube video.

        Args:
            video_url (str): URL of the YouTube video.

        Returns:
            str: Transcript text in plain format.

        Raises:
            Exception: If transcript download fails.
        """
        transcript_text = self.download_transcript_from_youtube(
            video_url=video_url,
            output_path=self.output_path,
        )
        logging.info("****Transcript downloaded and saved****")

        return transcript_text

    def get_text_from_youtube(self, video_url: str, markdown_output: bool = True, **kwargs) -> dict:
        """
        Get and optionally format transcript from a YouTube video using a language model.

        Args:
            video_url (str): URL of the YouTube video.
            markdown_output (bool, optional): Whether to return the result in Markdown format.

        Returns:
            dict: Dictionary containing:
                - text (str): Final processed transcript.
                - completion_tokens (int): Number of tokens used in generation.
                - prompt_tokens (int): Number of prompt tokens used.
                - completion_model (str): Name of the model used.
                - completion_model_provider (str): Provider of the model.
                - text_chunks (optional): List of processed chunks if `save_transcript_chunks` is True.

        Raises:
            Exception: If there is an error during transcript extraction or LLM processing.
        """

        transcript_text = self.download_transcript(video_url)
        logging.info("****Transcript text obtained****")

        result_dict = text_to_md(
            transcript_text=transcript_text,
            markdown_output=markdown_output,
            llm_api_key=self.llm_api_key,
            output_path=self.output_path,
            save_transcript_chunks=self.save_transcript_chunks
        )

        result_dict["type"] = self.type

        return result_dict

    def load(self, input_list: list[str], markdown_output: bool = True, **kwargs) -> dict:
        """
        Extract text from a YouTube video.

        Args:
            input_list (list[str]): A list containing one YouTube video URLs.
            markdown_output (bool, default: True): Whether to format the extracted text as Markdown.
            **kwargs: Additional options passed to the extractor.

        Returns:
            dict: A dictionary containing the extracted text and metadata.
        """
        return self.get_text_from_youtube(video_url=input_list[0], markdown_output=markdown_output, **kwargs)