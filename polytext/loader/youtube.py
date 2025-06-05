# Standard library imports
import os
import tempfile
import logging

# External library imports
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, InvalidVideoId, VideoUnavailable, TranslationLanguageNotAvailable, NoTranscriptFound, NotTranslatable, YouTubeRequestFailed, RequestBlocked, AgeRestricted
from xml.etree.ElementTree import ParseError
from requests.exceptions import ConnectionError
from retry import retry
import yt_dlp

# Local imports
from ..converter.text_to_md import text_to_md
from ..converter.audio_to_text import transcribe_full_audio
from ..exceptions import EmptyDocument

logger = logging.getLogger(__name__)

MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED = int(os.getenv("MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED", "200"))

class YoutubeTranscriptLoader:
    """
    Class to download, and process transcripts from YouTube videos.
    """

    def __init__(self, llm_api_key: str = None, markdown_output: bool = True, temp_dir: str = 'temp',
                 save_transcript_chunks: bool = False, **kwargs) -> None:
        """
        Initialize YoutubeTranscriptLoader class with API key and configuration.

        Args:
            llm_api_key (str, optional): API key for the LLM used for processing.
            save_transcript_chunks (bool, optional): Whether to include processed chunks in final output.
            markdown_output (bool, default: True): Whether to format the extracted text as Markdown.
            temp_dir (str, optional): Temporary directory to store intermediate transcript files.
        """
        self.llm_api_key = llm_api_key
        self.save_transcript_chunks = save_transcript_chunks
        self.temp_dir = temp_dir
        self.markdown_output = markdown_output
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
            EmptyDocument: If subtitles are disabled or not found.
            Exception: For other errors.
        """
        ytt_api = YouTubeTranscriptApi()
        video_id = self.extract_video_id(video_url)

        transcripts = ytt_api.list(video_id)
        # Get the available languages of the transcript
        languages = [t.language_code for t in transcripts]
        logging.info("****Fetching transcript from YouTube****")
        transcript_data = ytt_api.fetch(video_id, languages)

        if not transcript_data or len(transcript_data) < MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED:
            raise EmptyDocument(f"No text found or text length is minor to {MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED} in the transcript fot this video: {video_url}")

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

    def get_text_from_youtube(self, video_url: str) -> dict:
        """
        Extract and process the transcript from a YouTube video.

        Attempts to fetch the transcript using the YouTube API. If subtitles are disabled,
        downloads the audio using yt-dlp and transcribes it with an LLM-based function.
        The result is optionally formatted as Markdown and may include chunked transcripts.

        Args:
            video_url (str): The URL of the YouTube video.

        Returns:
            dict: A dictionary containing:
                - text (str): The final processed transcript.
                - completion_tokens (int): Number of tokens used in LLM generation (if applicable).
                - prompt_tokens (int): Number of prompt tokens used (if applicable).
                - completion_model (str): Name of the LLM model used (if applicable).
                - completion_model_provider (str): Provider of the LLM model (if applicable).
                - text_chunks (optional): List of processed transcript chunks if `save_transcript_chunks` is True.
                - type (str): The loader type ("YouTube").
                - input (str): The input video URL.

        Raises:
            EmptyDocument: If subtitles are disabled and audio download or transcription fails.
            Exception: For other errors during transcript extraction or LLM processing.
        """
        try:
            transcript_text = self.download_transcript(video_url)
            logging.info("****Transcript text obtained****")

            result_dict = text_to_md(
                transcript_text=transcript_text,
                markdown_output=self.markdown_output,
                llm_api_key=self.llm_api_key,
                output_path=self.output_path,
                save_transcript_chunks=self.save_transcript_chunks
            )

            result_dict["type"] = self.type

        except (EmptyDocument, TranscriptsDisabled, TranslationLanguageNotAvailable, NoTranscriptFound, NotTranslatable, YouTubeRequestFailed, RequestBlocked) as e:
            logging.info(
                f"Subtitles are disabled for this video: {video_url}. Falling back to YT-DLP.", e)

            output_dir = self.temp_dir
            video_id = self.extract_video_id(video_url)
            os.makedirs(output_dir, exist_ok=True)
            output_template = os.path.join(output_dir, f"{video_id}")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])

                # Find the downloaded audio file
                audio_path = os.path.join(output_dir, f"{video_id}.mp3")

                result_dict = transcribe_full_audio(
                    audio_file=audio_path,
                    markdown_output=self.markdown_output,
                    llm_api_key=self.llm_api_key,
                    save_transcript_chunks=self.save_transcript_chunks,
                )

                result_dict["type"] = "youtube_audio"

                if os.path.exists(audio_path):
                    os.remove(audio_path)
                    logger.info(f"Deleted temporary audio file: {audio_path}")

            except yt_dlp.utils.DownloadError as e:
                logger.error(f"Failed to download audio with yt-dlp: {e}", exc_info=True)
                raise EmptyDocument(f"Could not download audio for this video: {video_url}")

            except Exception as e:
                logger.error(f"Unexpected error during audio download: {e}", exc_info=True)
                raise e

        except (InvalidVideoId, VideoUnavailable, AgeRestricted) as e:
            logger.error(f"Invalid, unavailable, age restricted video: {video_url}", exc_info=True)
            raise e

        result_dict["input"] = video_url
        return result_dict

    def load(self, input_path: str) -> dict:
        """
        Extract text from a YouTube video.

        Args:
            input_path (list[str]): A list containing one YouTube video URLs.

        Returns:
            dict: A dictionary containing the extracted text and metadata.
        """
        return self.get_text_from_youtube(video_url=input_path)