# Standard library imports
import os
import logging
import time
import re
from collections import Counter

# External library imports
from retry import retry
from google.genai import types
from google import genai
from google.genai import errors
from google.api_core import exceptions as google_exceptions
from ..prompts.transcription import VIDEO_TO_MARKDOWN_PROMPT, VIDEO_TO_TEXT_PROMPT

# Local imports
from ..exceptions import EmptyDocument, LoaderTimeoutError

logger = logging.getLogger(__name__)

MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED = int(os.getenv("MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED", "200"))
YOUTUBE_MAX_OUTPUT_TOKENS = int(os.getenv("YOUTUBE_MAX_OUTPUT_TOKENS", "32000"))
YOUTUBE_MIN_OUTPUT_TOKENS = 500
YOUTUBE_TAIL_REPETITION_LINES = int(os.getenv("YOUTUBE_TAIL_REPETITION_LINES", "200"))
YOUTUBE_TAIL_REPETITION_THRESHOLD = float(os.getenv("YOUTUBE_TAIL_REPETITION_THRESHOLD", "0.35"))
YOUTUBE_FALLBACK_SOURCE_PATTERN = os.getenv("YOUTUBE_FALLBACK_SOURCE_PATTERN", "flash-lite-preview")
YOUTUBE_FALLBACK_MODEL = os.getenv("YOUTUBE_FALLBACK_MODEL", "models/gemini-3-flash-preview")
YOUTUBE_FALLBACK_TEMPERATURE = 1.0
YOUTUBE_FINAL_FALLBACK_MODEL = os.getenv("YOUTUBE_FINAL_FALLBACK_MODEL", "models/gemini-2.5-flash")


def normalize_text_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [normalize_text_line(chunk) for chunk in chunks if normalize_text_line(chunk)]


def repetition_ratio(items: list[str], min_occurrences: int = 2) -> float:
    if not items:
        return 0.0

    counts = Counter(items)
    repeated_items = sum(count for count in counts.values() if count >= min_occurrences)
    return repeated_items / len(items)


def tail_has_excessive_repetition(text: str, tail_lines: int = YOUTUBE_TAIL_REPETITION_LINES) -> bool:
    if not text:
        return False

    lines = [normalize_text_line(line) for line in text.splitlines() if normalize_text_line(line)]
    tail = lines[-tail_lines:] if len(lines) > tail_lines else lines
    if len(tail) >= 4 and repetition_ratio(tail) >= YOUTUBE_TAIL_REPETITION_THRESHOLD:
        return True

    sentences = split_sentences("\n".join(tail))
    if len(sentences) >= 4 and repetition_ratio(sentences) >= YOUTUBE_TAIL_REPETITION_THRESHOLD:
        return True

    return False


def extract_finish_reason(response) -> str | None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None

    finish_reason = getattr(candidates[0], "finish_reason", None)
    if finish_reason is None:
        return None
    return str(finish_reason).upper()


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

    def __init__(self, llm_api_key: str = None, model="models/gemini-3.1-flash-lite-preview", model_provider="google", markdown_output: bool = True, temp_dir: str = 'temp',
                 save_transcript_chunks: bool = False, timeout_minutes: int = None, **kwargs) -> None:
        """
        Initialize the YoutubeTranscriptLoaderWithLlm class with API key and configuration.

        Args:
            llm_api_key (str, optional): API key for the LLM used for processing.
            model (str, optional): Name of the LLM model used for transcription (default: "models/gemini-3.1-flash-lite-preview").
            model_provider (str, optional): Provider of the LLM model (default: "google").
            markdown_output (bool, optional): Whether to format the extracted text as Markdown (default: True).
            temp_dir (str, optional): Temporary directory to store intermediate transcript files (default: 'temp').
            save_transcript_chunks (bool, optional): Whether to include processed chunks in the final output (default: False).
            timeout_minutes (int, optional): Timeout in minutes for LLM response (default: None).
        """
        self.llm_api_key = llm_api_key
        self.model = model
        self.model_provider = model_provider
        self.save_transcript_chunks = save_transcript_chunks
        self.temp_dir = temp_dir
        self.markdown_output = markdown_output
        self.type = "youtube_url"
        self.temp_dir = os.path.abspath(temp_dir)
        self.timeout_minutes = timeout_minutes
        self.max_output_tokens = max(YOUTUBE_MAX_OUTPUT_TOKENS, YOUTUBE_MIN_OUTPUT_TOKENS)
        self.fallback_source_pattern = YOUTUBE_FALLBACK_SOURCE_PATTERN
        self.fallback_model = YOUTUBE_FALLBACK_MODEL
        self.fallback_temperature = YOUTUBE_FALLBACK_TEMPERATURE
        self.final_fallback_model = YOUTUBE_FINAL_FALLBACK_MODEL

    def should_fallback_temperature_retry(self, error: EmptyDocument, temperature: float) -> bool:
        if error.code not in (997, 999, 996):
            return False
        if self.fallback_model == self.model and temperature == self.fallback_temperature:
            return False
        if self.fallback_source_pattern not in self.model:
            return False
        return True

    def run_fallback(self, video_url: str, reason: str, fallback_model: str, fallback_temperature: float) -> dict:
        logger.info(
            "Retrying YouTube transcript with fallback model %s and temperature %s for %s because %s",
            fallback_model,
            fallback_temperature,
            video_url,
            reason,
        )
        fallback_loader = YoutubeTranscriptLoaderWithLlm(
            llm_api_key=self.llm_api_key,
            model=fallback_model,
            model_provider=self.model_provider,
            markdown_output=self.markdown_output,
            temp_dir=self.temp_dir,
            save_transcript_chunks=self.save_transcript_chunks,
            timeout_minutes=self.timeout_minutes,
        )
        result = fallback_loader.get_text_from_youtube(
            video_url=video_url,
            temperature=fallback_temperature,
        )
        result["fallback_from_model"] = self.model
        result["fallback_to_model"] = fallback_model
        result["fallback_reason"] = reason
        result["fallback_temperature"] = fallback_temperature
        return result

    def should_final_fallback_model(self, error: EmptyDocument) -> bool:
        if error.code not in (997, 999, 996):
            return False
        if self.final_fallback_model == self.model:
            return False
        return self.model == self.fallback_model

    def build_config(self, output_budget: int, prompt_template: str, temperature: float = 0.0) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
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
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
            http_options=(
                types.HttpOptions(timeout=self.timeout_minutes * 60_000)
                if self.timeout_minutes is not None else None
            ),
            thinking_config=types.ThinkingConfig(
                thinking_budget=0,
            ),
            temperature=temperature,
            max_output_tokens=output_budget,
            system_instruction=[prompt_template]
        )

    @retry(
        (
                google_exceptions.DeadlineExceeded,
                google_exceptions.ResourceExhausted,
                google_exceptions.ServiceUnavailable,
                google_exceptions.InternalServerError,
                errors.ServerError,
                errors.APIError,
        ),
        tries=8,
        delay=1,
        backoff=2,
        logger=logger,
    )
    def get_text_from_youtube(self, video_url: str, temperature: float = 0.0) -> dict:
        """
        Extract and process the transcript from a YouTube video using Gemini API.

        Args:
            video_url (str): The URL of the YouTube video.
            temperature (float): The LLM temperature. Default 0.0

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

        start = None
        timeout_s = None
        try:
            start = time.monotonic()
            timeout_s = None if self.timeout_minutes is None else self.timeout_minutes * 60

            logger.info(
                "Gemini YouTube attempt 1 using output budget %s",
                self.max_output_tokens,
            )
            response = client.models.generate_content(
                model=self.model,
                contents=types.Content(
                    parts=[
                        types.Part(file_data=types.FileData(file_uri=video_url)),
                    ]
                ),
                config=self.build_config(self.max_output_tokens, prompt_template, temperature),
            )
            response_text = response.text or ""
            finish_reason = extract_finish_reason(response)
            has_repetitive_tail = tail_has_excessive_repetition(response_text)
            used_output_budget = self.max_output_tokens

            if finish_reason and "MAX_TOKENS" in finish_reason:
                logger.info(
                    "Gemini YouTube hit MAX_TOKENS with output budget %s on model %s",
                    self.max_output_tokens,
                    self.model,
                )

            if has_repetitive_tail:
                logger.info(
                    "Gemini YouTube detected repetitive tail with output budget %s on model %s",
                    self.max_output_tokens,
                    self.model,
                )

            end_time = time.time()
            time_elapsed = end_time - start_time
            usage_metadata = getattr(response, "usage_metadata", None)
            prompt_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
            completion_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0
            total_tokens = getattr(usage_metadata, "total_token_count", 0) or 0

            if response.usage_metadata:
                print(f"Token in prompt: {prompt_tokens}")
                print(f"Token in output: {completion_tokens}")
                print(f"Token total: {total_tokens}")
                print(f"Response text length: {len(response_text)}")

            if finish_reason and "RECITATION" in finish_reason:
                raise EmptyDocument(
                    message=f"Transcript blocked because recitation was detected for video: {video_url}",
                    code=996,
                )

            if finish_reason and "MAX_TOKENS" in finish_reason:
                raise EmptyDocument(
                    message=f"Transcript truncated because max output tokens were reached for video: {video_url}",
                    code=999,
                )

            if has_repetitive_tail:
                raise EmptyDocument(
                    message=f"Transcript discarded because repetitive tail was detected for video: {video_url}",
                    code=997,
                )

            # Text below minimum threshold or not found
            if response_text and "no human speech detected" not in response_text.lower() and len(response_text) < MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED:
                message = f"No text found or text length is minor to {MIN_YOUTUBE_TEXT_LENGTH_ACCEPTED} in the transcript fot this video: {video_url}"
                logger.info(message)
                raise EmptyDocument(message=message, code=998)

            result_dict = {"text": response_text if response_text and "no human speech detected" not in response_text.lower() else "",
                           "completion_tokens": completion_tokens,
                           "prompt_tokens": prompt_tokens,
                           "completion_model": self.model,
                           "completion_model_provider": self.model_provider,
                           "text_chunks": "not provided",
                           "type": "youtube_gemini",
                           "input": video_url,
                           "finish_reason": finish_reason,
                           "max_output_tokens": used_output_budget,
                           "temperature": temperature}

            logger.info(f"Gemini - YouTube performed using {self.model} in {time_elapsed:.2f} seconds")
            return result_dict
        except EmptyDocument as e:
            if self.should_fallback_temperature_retry(e, temperature):
                return self.run_fallback(
                    video_url=video_url,
                    reason=e.message,
                    fallback_model=self.fallback_model,
                    fallback_temperature=self.fallback_temperature,
                )
            if self.should_final_fallback_model(e):
                return self.run_fallback(
                    video_url=video_url,
                    reason=e.message,
                    fallback_model=self.final_fallback_model,
                    fallback_temperature=0.0,
                )
            raise

        except errors.ClientError as e:
            if e.status == 'INVALID_ARGUMENT':
                raise Exception(f"Invalid argument: {e.message}")
            else:
                raise e

        except errors.ServerError as e:
            code = getattr(e, "code", None)
            status = getattr(e, "status", None)
            msg = str(getattr(e, "message", "")) or str(e)
            elapsed = time.monotonic() - start

            if code == 503 or status == "UNAVAILABLE" or "UNAVAILABLE" in msg:
                logger.info("Transient Gemini server error for YouTube transcript: %s", msg)
                raise

            # canonical server timeout
            if code == 504 or status == "DEADLINE_EXCEEDED" or "DEADLINE_EXCEEDED" in msg:
                raise LoaderTimeoutError()

            # timeout-ish INTERNAL: treat as timeout if it lands near our deadline
            if timeout_s is not None and elapsed >= max(0, timeout_s - 1) and status == "INTERNAL":
                raise LoaderTimeoutError()

            # otherwise, let higher layers retry/handle
            raise

    def load(self, input_path: str) -> dict:
        """
        Extract text from a YouTube video.

        Args:
            input_path (list[str]): A list containing one YouTube video URLs.

        Returns:
            dict: A dictionary containing the extracted text and metadata.
        """
        return self.get_text_from_youtube(video_url=input_path)
