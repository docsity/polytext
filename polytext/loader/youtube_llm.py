# Standard library imports
import os
import logging
import time

# External library imports
from retry import retry
from google.genai import types
from google import genai
from google.genai import errors
from google.api_core import exceptions as google_exceptions
from ..prompts.transcription import VIDEO_TO_MARKDOWN_PROMPT, VIDEO_TO_TEXT_PROMPT

# Local imports
from ..exceptions import EmptyDocument

logger = logging.getLogger(__name__)

MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED = int(os.getenv("MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED", "200"))

class YoutubeTranscriptLoaderWithLlm:
    """
    Class to download and process transcripts from YouTube videos using Gemini API.

    This class provides functionality to extract text from YouTube videos by leveraging
    a Large Language Model (LLM) for transcription. It supports both Markdown and plain text
    output formats and includes safety settings for content generation.

    Attributes:
        llm_api_key (str): API key for the LLM used for processing.
        model (str): Name of the LLM model used for transcription.
        model_provider (str): Provider of the LLM model (default: "google").
        markdown_output (bool): Whether to format the extracted text as Markdown.
        temp_dir (str): Temporary directory to store intermediate transcript files.
        save_transcript_chunks (bool): Whether to include processed chunks in the final output.
        type (str): Loader type identifier ("youtube_gemini").
    """

    def __init__(self, llm_api_key: str = None, model="models/gemini-2.5-flash-preview-05-20", model_provider="google", markdown_output: bool = True, temp_dir: str = 'temp',
                 save_transcript_chunks: bool = False, **kwargs) -> None:
        """
        Initialize the YoutubeTranscriptLoaderWithLlm class with API key and configuration.

        Args:
            llm_api_key (str, optional): API key for the LLM used for processing.
            model (str, optional): Name of the LLM model used for transcription (default: "models/gemini-2.5-flash-preview-05-20").
            model_provider (str, optional): Provider of the LLM model (default: "google").
            markdown_output (bool, optional): Whether to format the extracted text as Markdown (default: True).
            temp_dir (str, optional): Temporary directory to store intermediate transcript files (default: 'temp').
            save_transcript_chunks (bool, optional): Whether to include processed chunks in the final output (default: False).
        """
        self.llm_api_key = llm_api_key
        self.model = model
        self.model_provider = model_provider
        self.save_transcript_chunks = save_transcript_chunks
        self.temp_dir = temp_dir
        self.markdown_output = markdown_output
        self.type = "youtube"
        self.temp_dir = os.path.abspath(temp_dir)

    @retry(
        (
                google_exceptions.DeadlineExceeded,
                google_exceptions.ResourceExhausted,
                google_exceptions.ServiceUnavailable,
                google_exceptions.InternalServerError
        ),
        tries=8,
        delay=1,
        backoff=2,
        logger=logger,
    )
    def get_text_from_youtube(self, video_url: str) -> dict:
        """
        Extract and process the transcript from a YouTube video using Gemini API.

        Args:
            video_url (str): The URL of the YouTube video.

        Returns:
            dict: A dictionary containing:
                - text (str): The final processed transcript.
                - completion_tokens (int): Number of tokens used in LLM generation (if applicable).
                - prompt_tokens (int): Number of prompt tokens used (if applicable).
                - completion_model (str): Name of the LLM model used (if applicable).
                - completion_model_provider (str): Provider of the LLM model (if applicable).
                - type (str): The loader type ("youtube_gemini").
                - input (str): The input video URL.

        Raises:
            errors.ClientError: If there is a client-side error, such as invalid arguments, permission issues, or resource exhaustion.
            errors.ServerError: If there is a server-side error during processing.
            errors.UnknownFunctionCallArgumentError: If an unknown argument is passed to a function call.
            errors.UnsupportedFunctionError: If the function is unsupported by the API.
            errors.FunctionInvocationError: If there is an error during function invocation.
        """
        start_time = time.time()

        if self.markdown_output:
            logger.info("Using prompt for markdown format")
            prompt_template = VIDEO_TO_MARKDOWN_PROMPT
        else:
            logger.info("Using prompt for plain text format")
            prompt_template = VIDEO_TO_TEXT_PROMPT

        if self.llm_api_key:
            logger.info("Using provided Google API key")
            client = genai.Client(api_key=self.llm_api_key)
        else:
            logger.info("Using Google API key from ENV")
            client = genai.Client()

        config = types.GenerateContentConfig(
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ],
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW
        )

        try:
            # Call Gemini API to process the video
            response = client.models.generate_content(
                model=self.model,
                contents=types.Content(
                    parts=[
                        types.Part(file_data=types.FileData(file_uri=video_url)),
                        types.Part(text=prompt_template)
                    ]
                ),
                config=config
            )

            end_time = time.time()
            time_elapsed = end_time - start_time

            if response.usage_metadata:
                print(f"Token in prompt: {response.usage_metadata.prompt_token_count}")
                print(f"Token in output: {response.usage_metadata.candidates_token_count}")
                print(f"Token total: {response.usage_metadata.total_token_count}")

            # Text below minimum threshold or not found
            if "no human speech detected" not in response.text.lower() and len(response.text) < MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED:
                message = f"No text found or text length is minor to {MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED} in the transcript fot this video: {video_url}"
                logger.info(message)
                raise EmptyDocument(message=message, code=998)

            result_dict = {"text": response.text if "no human speech detected" not in response.text.lower() else "",
                           "completion_tokens": response.usage_metadata.candidates_token_count,
                           "prompt_tokens": response.usage_metadata.prompt_token_count,
                           "completion_model": self.model,
                           "completion_model_provider": self.model_provider,
                           "text_chunks": "not provided",
                           "type": "youtube_gemini", "input": video_url}

            logger.info(f"Gemini - YouTube performed using {self.model} in {time_elapsed:.2f} seconds")
            return result_dict

        except errors.ClientError as e:
            if e.status == 'INVALID_ARGUMENT':
                raise Exception(f"Invalid argument: {e.message}")
            else:
                raise e

    def load(self, input_path: str) -> dict:
        """
        Extract text from a YouTube video.

        Args:
            input_path (list[str]): A list containing one YouTube video URLs.

        Returns:
            dict: A dictionary containing the extracted text and metadata.
        """
        return self.get_text_from_youtube(video_url=input_path)