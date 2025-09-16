# Standard library imports
import os
import logging
import dotenv
import mimetypes
import json
import httpx
import httpcore
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Local imports
from ..loader import (
    OCRLoader,
    DocumentLoader,
    VideoLoader,
    AudioLoader,
    HtmlLoader,
    PlainTextLoader,
    DocumentOCRLoader,
    MarkdownLoader,
    YoutubeTranscriptLoaderWithLlm
)
from ..exceptions import EmptyDocument, LoaderTimeoutError, LoaderError
from ..utils.utils import remove_markdown_strip

# External imports
import boto3
from google.cloud import storage
from google.genai import errors as genai_errors


dotenv.load_dotenv()

logger = logging.getLogger(__name__)

MIN_DOC_TEXT_LENGTH_ACCEPTED = int(os.getenv("MIN_DOC_TEXT_LENGTH_ACCEPTED", "400"))


class BaseLoader:
    def __init__(self, markdown_output=True, llm_api_key=None, provider: str = "google", temp_dir: str = "temp",
                 timeout_minutes: int | None = None, **kwargs):
        """
        Initialize the BaseLoader with cloud storage and LLM configurations.

        Handles document loading and storage operations across AWS S3 and Google Cloud Storage.
        Sets up temporary directory for processing files.

        Args:.
            markdown_output (bool, optional): If True, the extracted text will be formatted as Markdown.
                Defaults to True.
            llm_api_key (str, optional): API key for language model service. Defaults to None.
            temp_dir (str, optional): Path for temporary file storage. Defaults to "temp".
            provider (str, optional): Provider of the model. Default to "google".
            timeout_minutes (int, optional): Timeout in minutes. Defaults to None.
             **kwargs: Additional keyword arguments to pass to the underlying loader or extraction logic.
                - target_size (int, optional): Target file size in bytes. Defaults to 1MB
                - source (str): Source of the document. Must be either "cloud" or "local"
                - fallback_ocr (bool, optional): If True, Optical Character Recognition (OCR) will be used as a fallback
                  if direct text extraction fails, particularly for image-based content. Defaults to True.
                - save_transcript_chunks (bool, optional): Whether to save chunk transcripts in final output. Defaults to False.
                - bitrate_quality (int, optional): Variable bitrate quality from 0-9 (9 being lowest). Defaults to 9

        Raises:
            ValueError: If cloud storage clients are provided without bucket names
            OSError: If temp directory creation fails
        """
        self.markdown_output = markdown_output
        self.llm_api_key = llm_api_key
        self.temp_dir = temp_dir
        self.provider = provider
        self.timeout_minutes = timeout_minutes
        self.kwargs = kwargs
        self.target_size = kwargs.get("target_size", 1)
        self.source = kwargs.get("source", "cloud")
        self.fallback_ocr = kwargs.get("fallback_ocr", False)
        self.save_transcript_chunks = kwargs.get("save_transcript_chunks", False)
        self.bitrate_quality = kwargs.get("bitrate_quality", 9)


    def get_text(self, input_list: list[str], **kwargs):
        """
        Extracts and aggregates text content from one or more input sources (URLs or file paths).

        This method determines the appropriate loader based on the first input, initializes any required
        storage clients, and processes the input(s) to extract text and related metadata. For multiple image
        inputs, extraction is parallelized and results are aggregated in the order of `input_list`.

        Args:
            input_list (list[str]): List of one or more input strings (URLs or file paths) to process.

        Keyword Args:
            Additional keyword arguments are passed to the loader class.

        Returns:
            dict: Aggregated extraction results with the following keys:
                - `text` (str): Concatenated extracted text from all sources, separated by newlines.
                - `completion_tokens` (int): Total completion tokens across all sources.
                - `prompt_tokens` (int): Total prompt tokens across all sources.
                - `output_list` (list): List of individual extraction results (one per input):
                        - `text` (str): Concatenated extracted text.
                        - `completion_tokens` (int): Total completion tokens.
                        - `prompt_tokens` (int): Total prompt tokens.
                        - `completion_model` (str): Model name used.
                        - `completion_model_provider` (str): Provider of the model.
                        - `text_chunks` (list): List of text chunks, if chunking was applied.
                        - `type` (str): Type of the processed source (e.g., ocr, video, audio, text).
                        - `input` (str): The input path or URL.

        Raises:
            TypeError: If `input_list` is not a list of strings.
            ValueError: If `input_list` is empty or contains unsupported input types.
        """

        if not isinstance(input_list, list) or not all(isinstance(item, str) for item in input_list):
            raise TypeError("Parameter 'input' must be a list of strings.")

        first_file_url = input_list[0]
        kwargs = {**self.kwargs, **kwargs}

        storage_client = self.initiate_storage(input=first_file_url)
        loader_class = self.init_loader_class(input=first_file_url, storage_client=storage_client, llm_api_key=self.llm_api_key, **kwargs)

        try:
            response = self.run_loader_class(loader_class=loader_class, input_list=input_list)
        except EmptyDocument as e:
            logger.info(f"Empty document encountered: {e.message}")
            if self.fallback_ocr:
                loader_class = self.init_loader_class(input=first_file_url, storage_client=storage_client,
                                                      llm_api_key=self.llm_api_key, is_document_fallback=True, **kwargs)
                response = self.run_loader_class(loader_class=loader_class, input_list=input_list)
            else:
                response = {"text": "", "completion_tokens": 0, "prompt_tokens": 0, "output_list": [
                    {"text": "", "completion_tokens": 0, "prompt_tokens": 0, "completion_model": "not provided",
                     "completion_model_provider": "not provided", "text_chunks": "not provided", "type": "document",
                     "input": first_file_url}]}
        except LoaderTimeoutError:
            logger.error("Timeout error encountered during loading.")
            raise LoaderError(message="timeout gemini", status=504, code="TIMEOUT")
        except (httpx.ReadTimeout,
                httpx.TimeoutException,
                httpcore.ReadTimeout,
                httpcore.TimeoutException) as e:
            logger.error("http timeout error encountered during loading.")
            raise LoaderError(message="timeout gemini", status=504, code="TIMEOUT")
        except genai_errors.ServerError as e:
            code = getattr(e, "code", None)
            status = getattr(e, "status", None)
            msg = str(getattr(e, "message", "")) or str(e)

            if code == 504 or status == "DEADLINE_EXCEEDED" or "DEADLINE_EXCEEDED" in msg:
                logger.error("Server error 504 encountered during loading.")
                raise LoaderError(message="timeout gemini", status=504, code="TIMEOUT")
            raise

        return response

    def initiate_storage(self, input: str) -> dict:
        """
            Initializes and returns a client and relevant details for various cloud storage services or web URLs.

            This method detects the type of input URL (S3, GCS, HTTP/S) and
            sets up the appropriate client for accessing the resource.

            Args:
                input (str): The URL string representing the file's location.
                             Supported schemes: "s3://", "gcs://", "http://", "https://", "www.", "www.youtube".

            Returns:
                dict: A dictionary containing the initialized storage client and parsed path details.
                      - For S3: keys include 's3_client' (boto3 client), 'document_aws_bucket' (bucket name),
                        and 'file_path' (path within the bucket).
                      - For GCS: keys include 'gcs_client' (google.cloud.storage.Client), 'document_gcs_bucket' (bucket name),
                        and 'file_path' (path within the bucket).
                      - For HTTP/HTTPS/WWW: an empty dictionary is returned, as no specific client initialization
                        is needed for direct web access at this stage.

            Raises:
                NotImplementedError: If the input URL scheme is not recognized or supported.
        """

        if input.startswith("s3://"):
            logger.info(f"Initiating S3 initialization for {input}")
            # Initialize S3 client
            s3_client = boto3.client("s3")
            s3_path = input.replace("s3://", "")
            parts = s3_path.split("/", 1)

            bucket = parts[0]
            file_path = parts[1] if len(parts) > 1 else ""

            return {
                "s3_client": s3_client,
                "document_aws_bucket": bucket,
                "file_path": file_path,
            }
        elif input.startswith("gcs://"):
            logger.info(f"Initializing GCS client for input: {input}")
            # Initialize GCS client
            gcs_client = storage.Client()
            gcs_path = input.replace("gcs://", "")
            parts = gcs_path.split("/", 1)

            bucket = parts[0]
            file_path = parts[1] if len(parts) > 1 else ""

            return {
                "gcs_client": gcs_client,
                "document_gcs_bucket": bucket,
                "file_path": file_path,
            }
        elif (
            input.startswith("http://")
            or input.startswith("https://")
            or input.startswith("www.")
            or input.startswith("www.youtube")
            or not  self.is_local_path(input)
            or self.source == "local"
        ):
            return dict()
        else:
            raise NotImplementedError

    def init_loader_class(self, input: str, storage_client: dict, llm_api_key: str, is_document_fallback: bool = False,
                          **kwargs) -> any:
        """
            Initializes and returns the appropriate content loader class based on the input URL's type.

            This method acts as a factory, inspecting the input URL's scheme and MIME type
            to determine which specific loader (e.g., YouTube transcript, HTML, Text, Audio, Video)
            is best suited to handle the content. It also merges storage client details into kwargs
            for loaders that might need them.

            Args:
                input (str): The URL string of the content to be loaded.
                storage_client (dict): A dictionary containing details and clients for cloud storage
                                        (e.g., S3 client, GCS client, bucket names) as returned by initiate_storage.
                llm_api_key (str): The API key for the LLM provider, necessary for loaders that
                                   interact with language models.
                is_document_fallback (bool): If True, the DocumentOCRLoader will be used as a fallback
                **kwargs: Additional keyword arguments to pass to the initialized loader class.
                          These will be merged with the `storage_client` dictionary.

            Returns:
                An instance of a concrete loader class (e.g., YoutubeTranscriptLoader,
                HtmlLoader, TextLoader, AudioLoader, VideoLoader).

            Raises:
                ValueError: If a recognized MIME type is encountered but is not supported by any specific loader.
                FileNotFoundError: If the input URL format is not recognized, or if it's a file path
                                   for which no suitable loader can be determined.
        """
        parsed_url = urlparse(input)
        mime_type, _ = mimetypes.guess_type(input)
        kwargs = {**kwargs, **storage_client}
        file_extension = None

        # Try extracting the extension from the URL or local path
        if parsed_url.scheme:  # If is URL (http, https, gs, s3, etc.)
            path_without_query = parsed_url.path
            if path_without_query:
                _, file_extension = os.path.splitext(path_without_query)
        else:  # If is local file path (without schema)
            if os.path.exists(input):
                _, file_extension = os.path.splitext(input)

        if file_extension:
            file_extension = file_extension.lower()

        if is_document_fallback:
            return DocumentOCRLoader(llm_api_key=llm_api_key, markdown_output=self.markdown_output, temp_dir=self.temp_dir, timeout_minutes=self.timeout_minutes, **kwargs)

        if parsed_url.scheme in ["http", "https"] or input.startswith("www."):
            if "youtube.com" in parsed_url.netloc or "youtu.be" in parsed_url.netloc:
                return YoutubeTranscriptLoaderWithLlm(llm_api_key=llm_api_key, markdown_output=self.markdown_output, temp_dir=self.temp_dir, timeout_minutes=self.timeout_minutes, **kwargs)
            else:
                return HtmlLoader(markdown_output=self.markdown_output)
        elif mime_type:
            if file_extension in [".pdf", ".xlsx", ".docx", ".txt", ".csv", ".odt", ".pptx", ".xls", ".doc", ".ppt", ".rtf"]:
                return DocumentLoader(markdown_output=self.markdown_output, temp_dir=self.temp_dir, timeout_minutes=self.timeout_minutes, **kwargs)
            elif mime_type.startswith("audio/"):
                return AudioLoader(llm_api_key=llm_api_key, markdown_output=self.markdown_output, temp_dir=self.temp_dir, timeout_minutes=self.timeout_minutes, **kwargs)
            elif mime_type.startswith("video/"):
                return VideoLoader(llm_api_key=llm_api_key, markdown_output=self.markdown_output, temp_dir=self.temp_dir, timeout_minutes=self.timeout_minutes, **kwargs)
            elif mime_type.startswith("image/"):
                return OCRLoader(llm_api_key=llm_api_key, markdown_output=self.markdown_output, temp_dir=self.temp_dir, timeout_minutes=self.timeout_minutes, **kwargs)
            elif mime_type.startswith("text/markdown"):
                return MarkdownLoader(markdown_output=self.markdown_output, temp_dir=self.temp_dir, **kwargs)
            elif mime_type == "text/html":
                return PlainTextLoader(
                    llm_api_key=llm_api_key,
                    markdown_output=self.markdown_output,
                    temp_dir=self.temp_dir,
                    **kwargs,
                )
            else:
                raise ValueError(f"Unsupported MIME type: {mime_type}")

        elif self.validate_user_text(text=input):
            return PlainTextLoader(
                llm_api_key=llm_api_key,
                markdown_output=self.markdown_output,
                temp_dir=self.temp_dir,
                **kwargs,
            )

        raise FileNotFoundError(f"Input not found or format not recognized: {input}")

    @staticmethod
    def parse_input(input_string: str):
        if not input_string:
            raise ValueError("The input string cannot be empty")

        if input_string.startswith("s3://"):
            prefix = "s3://"
        elif input_string.startswith("gcs://"):
            prefix = "gcs://"
        else:
            return {"file_path": input_string}

        path = input_string.replace(prefix, "")
        parts = path.split("/", 1)
        bucket = parts[0]

        file_path = parts[1] if len(parts) > 1 else ""
        return {
            "file_url": input_string,
            "bucket": bucket,
            "file_path": file_path
        }

    def run_loader_class(self, loader_class: any, input_list: list[str]) -> dict:
        """
        Executes the provided loader class to extract and aggregate content from one or more input sources.

        Handles both single and multiple input cases. For multiple image inputs, extraction is parallelized and results are aggregated in order. For other types, only single input is supported. Aggregates text, token counts, and model metadata from the processed sources.

        Args:
            loader_class (object): An instance of a content loader class (e.g., HtmlLoader, OCRLoader, AudioLoader) capable of processing the input type.
            input_list (list[str]): List of one or more input strings (URLs or file paths) to process.

        Returns:
            dict: Aggregated extraction results with the following keys:
                - text (str): Concatenated extracted text from all sources, separated by newlines.
                - completion_tokens (int): Total completion tokens across all sources.
                - prompt_tokens (int): Total prompt tokens across all sources.
                - completion_model (str): Model name used, from the first processed source.
                - completion_model_provider (str): Provider of the model, from the first processed source.
                - text_chunks (list, optional): List of text chunks, if chunking was applied.
                - type (str): Type of the processed source (e.g., ocr, video, audio, text).
                - input (str): The input path or URL of the first processed source.
                - output_list (list): List of individual extraction results (one per input).

        Raises:
            ValueError: If input_list is empty or contains unsupported input types for multi-input processing.
        """

        result_dict = {}

        # Empty Input
        if not input_list:
            raise ValueError("Input list is empty.")

        first_mime_type, _ = mimetypes.guess_type(input_list[0])
        is_multi_input = len(input_list) > 1
        is_image_type = first_mime_type and first_mime_type.startswith("image")

        # More images inputs (parallelization)
        if is_multi_input and is_image_type:
            with ThreadPoolExecutor() as executor:
                # Associate each future with its original index
                future_to_index = {
                    executor.submit(loader_class.load, input_path=self.parse_input(input_string=s)["file_path"]): idx
                    for idx, s in enumerate(input_list)
                }

                # Prepare a list for the results, sorted by index
                results = [None] * len(input_list)
                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    results[idx] = future.result()

                # Rebuild result_dict keeping the order
                result_dict["text"] = "\n".join(r.get("text", "") for r in results)
                result_dict["completion_tokens"] = sum(r.get("completion_tokens", 0) for r in results)
                result_dict["prompt_tokens"] = sum(r.get("prompt_tokens", 0) for r in results)
                result_dict["completion_model"] = results[0].get("completion_model", "not provided")
                result_dict["completion_model_provider"] = results[0].get("completion_model_provider", "not provided")
                result_dict["text_chunks"] = results[0].get("text_chunks", "not provided")
                result_dict["type"] = results[0].get("type", "not provided")
                result_dict["input"] = results[0].get("input", "not provided")

        elif is_multi_input and not is_image_type:
            error_msg = f"Unsupported input: multiple inputs ({len(input_list)} provided) are not all image types (first type: {first_mime_type}). Multi-threading is only supported for multiple images."
            logger.info(error_msg)
            raise ValueError(error_msg)

        else:
            result_dict = loader_class.load(input_path=self.parse_input(input_string=input_list[0])["file_path"])

        result_dict = {
            "text": remove_markdown_strip(result_dict["text"]),
            "completion_tokens": result_dict["completion_tokens"],
            "prompt_tokens": result_dict["prompt_tokens"],
            "output_list": [result_dict],
        }

        return result_dict

# Helper methods
    @staticmethod
    def is_local_path(s: str) -> bool:
        if not s or "\n" in s or len(s) > 255:
            return False
        p = Path(s)
        if p.is_absolute() or (p.parts and p.parts[0] in (".", "..")) or "/" in s or "\\" in s:
            return True
        return False

    def validate_user_text(self, text: str) -> bool:
        """
        Validate a text string. Raises EmptyDocument if the text is too short.

        Args:
            self: The instance of the class.
            text (str): The text to validate.

        Returns:
            bool: True if the text is valid.

        Raises:
            EmptyDocument: If the text is shorter than the minimum accepted length.
        """
        cleaned_text = text.strip()
        is_local_path = self.is_local_path(cleaned_text)
        if not is_local_path and len(cleaned_text) < MIN_DOC_TEXT_LENGTH_ACCEPTED:
            message = f"Document text with less than {MIN_DOC_TEXT_LENGTH_ACCEPTED} characters"
            raise EmptyDocument(message=message, code=998)
        return True