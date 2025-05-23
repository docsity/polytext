# Standard library imports
import os
import logging
import dotenv
import mimetypes
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Local imports
from ..loader import TextLoader, VideoLoader, AudioLoader, YoutubeTranscriptLoader, HtmlLoader

# External imports
import boto3
from google.cloud import storage


dotenv.load_dotenv()

logger = logging.getLogger(__name__)


class BaseLoader:

    def get_text(self, input_list: list[str], markdown_output: bool = True, fallback_ocr: bool = True,
                  provider: str = "google", llm_api_key: str = None, **kwargs):
        """
            Extracts text content from one or more specified URLs (only for images), with optional formatting and OCR fallback.

            Args:
                input_list (list[str]): A list of one or more URLs (strings) from which to extract text.
                markdown_output (bool, optional): If True, the extracted text will be formatted as Markdown. Defaults to True.
                fallback_ocr (bool, optional): If True, Optical Character Recognition (OCR) will be used as a fallback
                                               if direct text extraction fails, particularly for image-based content.
                                               Defaults to True.
                provider (str, optional): The name of the AI provider to use for text extraction or OCR.
                                          Defaults to "google".
                llm_api_key (str, optional): The API key required for authentication with the chosen LLM provider.
                                             Defaults to None.
                **kwargs: Additional keyword arguments to pass to the underlying loader or extraction logic.

            Returns:
                dict: A dictionary containing the aggregated extracted data. The structure is as follows:
              - **"text"** (str): All extracted text content, concatenated with a newline for each new source
                                  when processing multiple URLs (only for images).
              - **"completion_tokens"** (int): The sum of completion tokens across all processed sources.
              - **"prompt_tokens"** (int): The sum of prompt tokens across all processed sources.
              - **"completion_model"** (str): The name of the completion model used, derived from the first
                                          processed source. Defaults to "not provided" if unavailable.
              - **"completion_model_provider"** (str): The provider of the completion model, derived from the first
                                                   processed source. Defaults to "not provided" if unavailable.

            Raises:
                TypeError: If the 'input' parameter is not a list of strings.
        """

        if not isinstance(input_list, list) or not all(isinstance(item, str) for item in input_list):
            raise TypeError("Parameter 'input' must be a list of strings.")

        first_file_url = input_list[0]

        storage_client = self.initiate_storage(input=first_file_url, **kwargs)
        loader_class = self.init_loader_class(input=first_file_url, storage_client=storage_client, llm_api_key=llm_api_key, **kwargs)

        return self.run_loader_class(loader_class=loader_class, input=input_list, markdown_output=markdown_output,
                            fallback_ocr=fallback_ocr, provider=provider, llm_api_key=llm_api_key, **kwargs)

    def initiate_storage(self, input: str, **kwargs) -> dict:
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
            # Initialize S3 client
            s3_client = boto3.client("s3")
            s3_path = input[0].replace("s3://", "")
            parts = s3_path.split("/", 1)  # divide solo al primo "/"

            bucket = parts[0]
            file_path = parts[1] if len(parts) > 1 else ""

            return {
                "s3_client": s3_client,
                "document_aws_bucket": bucket,
                "file_path": file_path,
            }
        elif input.startswith("gcs://"):
            # Initialize GCS client
            gcs_client = storage.Client()
            gcs_path = input.replace("gcs://", "")
            parts = gcs_path.split("/", 1)  # divide solo al primo "/"

            bucket = parts[0]
            file_path = parts[1] if len(parts) > 1 else ""

            return {
                "gcs_client": gcs_client,
                "document_gcs_bucket": bucket,
                "file_path": file_path,
            }
        elif input.startswith("http://") or input.startswith("https://") or input.startswith("www.") or input.startswith("www.youtube") or kwargs.get('source'):
            return dict()
        else:
            raise NotImplementedError

    @staticmethod
    def init_loader_class(input: str, storage_client: dict, llm_api_key: str, **kwargs) -> any:
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
                **kwargs: Additional keyword arguments to pass to the initialized loader class.
                          These will be merged with the `storage_client` dictionary.

            Returns:
                AbstractLoaderBase: An instance of a concrete loader class (e.g., YoutubeTranscriptLoader,
                                    HtmlLoader, TextLoader, AudioLoader, VideoLoader) that inherits from
                                    AbstractLoaderBase, configured for the given input.

            Raises:
                ValueError: If a recognized MIME type is encountered but is not supported by any specific loader.
                FileNotFoundError: If the input URL format is not recognized, or if it's a file path
                                   for which no suitable loader can be determined.
        """
        parsed = urlparse(input)
        mime_type, _ = mimetypes.guess_type(input)
        kwargs = {**kwargs, **storage_client}

        # 1. URL - YouTube o Web
        if parsed.scheme in ["http", "https"]:
            if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
                return YoutubeTranscriptLoader(llm_api_key=llm_api_key, **kwargs)
            else:
                return HtmlLoader()
        # 2. Path file
        elif mime_type:
            if mime_type.startswith("text"):
                return TextLoader(**kwargs)
            elif mime_type.startswith("audio"):
                return AudioLoader(llm_api_key=llm_api_key, **kwargs)
            elif mime_type.startswith("video"):
                return VideoLoader(llm_api_key=llm_api_key, **kwargs)
            # elif mime_type.startswith("image"):
            #     return ImageLoader()
            else:
                raise ValueError(f"Unsupported MIME type: {mime_type}")

        raise FileNotFoundError(f"Input not found or format not recognized: {input}")

    @staticmethod
    def parse_input(input_list: list[str]):
        if not input_list:
            raise ValueError("The input list cannot be empty")

        if input_list[0].startswith("s3://"):
            prefix = "s3://"
        elif input_list[0].startswith("gcs://"):
            prefix = "gcs://"
        else:
            return {"file_path": input_list}

        path = input_list[0].replace(prefix, "")
        parts = path.split("/", 1)
        bucket = parts[0]

        # Single element case
        if len(input_list) == 1:
            file_path = parts[1] if len(parts) > 1 else ""
            return {
                "file_url": input_list[0],
                "bucket": bucket,
                "file_path": file_path
            }

        # Case with multiple elements
        file_paths = []

        for path in input_list:
            path_clean = path.replace(prefix, "")
            path_parts = path_clean.split("/", 1)
            file_path = path_parts[1] if len(path_parts) > 1 else ""
            file_paths.append(file_path)

        return {
            "file_url": input_list[0],
            "bucket": bucket,
            "file_path": file_paths
        }

    def run_loader_class(self, loader_class: any, input: list[str], markdown_output: bool = True, fallback_ocr: bool = True,
                         provider: str = "google", llm_api_key: str = None, **kwargs ) -> dict:
        """
             Executes the appropriate loader class to extract content from input URLs,
             handling single or multiple image inputs with aggregation.

             This static method acts as a central execution point for content loaders.
             It intelligently handles cases where multiple image URLs are provided,
             aggregating their extracted text and token counts, while retaining model
             information from the first processed source.

             Args:
                 self:
                 loader_class (object): An instance of a content loader class
                                                    (e.g., HtmlLoader, ImageLoader) that
                                                    knows how to load the specific content type.
                 input (list[str]): A list of one or more URLs (strings) to process.
                 markdown_output (bool, optional): If True, the extracted text will be
                                                   formatted as Markdown. Defaults to True.
                 fallback_ocr (bool, optional): If True, OCR will be used as a fallback
                                                for image-based content. Defaults to True.
                 provider (str, optional): The AI provider to use. Defaults to "google".
                 llm_api_key (str, optional): The API key for the LLM provider. Defaults to None.
                 **kwargs: Additional keyword arguments to pass to the loader's `load` method.

             Returns:
                 dict: A dictionary containing the extracted content and metadata.
                       The structure is:
                       - **"text"** (str): Aggregated text from all processed inputs,
                                           with each new source separated by a newline.
                       - **"completion_tokens"** (int): Sum of completion tokens.
                       - **"prompt_tokens"** (int): Sum of prompt tokens.
                       - **"completion_model"** (str): Model name from the first processed source.
                       - **"completion_model_provider"** (str): Model provider from the first processed source.
         """

        result_dict = {}

        # Empty Input
        if not input:
            raise ValueError("Input list is empty.")

        first_mime_type, _ = mimetypes.guess_type(input[0])
        is_multi_input = len(input) > 1
        is_image_type = first_mime_type and first_mime_type.startswith("image")

        # More images inputs (parallelization)
        if is_multi_input and is_image_type:
            with ThreadPoolExecutor() as executor:
                # Map each URL to a future call of the load method
                futures = {executor.submit(loader_class.load, input_list=self.parse_input(input_list=[s])["file_path"], markdown_output=markdown_output, **kwargs): s for s in input}

                is_first_iteration = True
                for future in as_completed(futures):
                    current_dict_result = future.result()

                    if is_first_iteration:
                        result_dict["text"] = current_dict_result.get("text", "")
                        result_dict["completion_tokens"] = current_dict_result.get("completion_tokens", 0)
                        result_dict["prompt_tokens"] = current_dict_result.get("completion_tokens", 0)
                        result_dict["completion_model"] = current_dict_result.get("completion_model", "not provided")
                        result_dict["completion_model_provider"] = current_dict_result.get("completion_model_provider", "not provided")
                        result_dict["text_chunks"] = current_dict_result.get("text_chunks", "not provided")

                        is_first_iteration = False
                    else:
                        result_dict["text"] += "\n" + current_dict_result.get("text", "")
                        result_dict["completion_tokens"] += current_dict_result.get("completion_tokens", 0)
                        result_dict["prompt_tokens"] += current_dict_result.get("prompt_tokens", 0)

        elif is_multi_input and not is_image_type:
            error_msg = f"Unsupported input: multiple inputs ({len(input)} provided) are not all image types (first type: {first_mime_type}). Multi-threading is only supported for multiple images."
            logger.error(error_msg)
            raise ValueError(error_msg)

        else:
            result_dict = loader_class.load(input_list=self.parse_input(input)["file_path"], markdown_output=markdown_output, **kwargs)

        return result_dict