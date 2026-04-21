# converter/ocr_to_text_azure_oai.py
import os
import logging
import tempfile
import time
import mimetypes
import base64

import ffmpeg
import httpx
from retry import retry

from openai import AzureOpenAI
from openai import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)

from ..prompts.ocr import OCR_TO_MARKDOWN_PROMPT, OCR_TO_PLAIN_TEXT_PROMPT

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    "image/png", "image/jpeg", "image/webp", "image/heic", "image/heif",
}


def compress_and_convert_image(input_path: str, target_size=1) -> str:
    """
    Compress and convert image files to PNG format using ffmpeg.

    Args:
        input_path (str): Path to the original image file
        target_size (int, optional): Target file size in MB. Defaults to 1MB.

    Returns:
        str: Path to the temporary compressed/converted PNG file
    """
    target_size_bytes = target_size * 1024 * 1024
    temp_dir = os.path.abspath("temp")
    os.makedirs(temp_dir, exist_ok=True)
    tempfile.tempdir = temp_dir

    try:
        fd, temp_image_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

        original_size = os.path.getsize(input_path)
        logger.info(f"Original image size: {original_size / 1024 / 1024:.2f}MB")

        if original_size > target_size_bytes:
            compression_ratio = (target_size_bytes / original_size) ** 0.5
            compression_ratio = max(0.01, min(compression_ratio, 1.0))

            logger.info(f"Compressing image with scale ratio ~{compression_ratio:.3f}")
            (
                ffmpeg.input(input_path)
                .output(
                    temp_image_path,
                    vf=f"scale=iw*{compression_ratio}:ih*{compression_ratio}",
                    compression_level=9,
                    threads=0,
                    loglevel="error",
                )
                .run(quiet=True, overwrite_output=True)
            )
        else:
            logger.info("Converting image to PNG without compression")
            (
                ffmpeg.input(input_path)
                .output(
                    temp_image_path,
                    compression_level=9,
                    threads=0,
                    loglevel="error",
                )
                .run(quiet=True, overwrite_output=True)
            )

        logger.info(f"Successfully processed image: {temp_image_path}")
        return temp_image_path

    except Exception as e:
        raise RuntimeError(f"FFmpeg error during image processing: {e}") from e


def get_ocr(file_for_ocr, markdown_output=False, llm_api_key=None, target_size=1, timeout_minutes=None):
    """
    Convenience function to extract text from an image file using OCR (Azure OpenAI),
    optionally formatted as Markdown.
    """
    converter = OCRToTextConverter(
        markdown_output=markdown_output,
        llm_api_key=llm_api_key,
        target_size=target_size,
        timeout_minutes=timeout_minutes,
    )
    return converter.get_ocr(file_for_ocr)


class OCRToTextConverter:
    def __init__(
        self,
        ocr_model="gpt-5-mini",
        ocr_model_provider="azure_openai",
        markdown_output=True,
        llm_api_key=None,
        target_size=1,
        temp_dir="temp",
        timeout_minutes=None,
        # Azure-specific (read from env by default)
        azure_endpoint=None,       # e.g. https://<resource>.openai.azure.com
        azure_api_version=None,    # e.g. "2024-10-21" (use your resource-supported version)
        max_tokens=4096,           # avoid truncation
    ):
        self.ocr_model = ocr_model
        self.ocr_model_provider = ocr_model_provider
        self.markdown_output = markdown_output
        self.llm_api_key = llm_api_key
        self.target_size = target_size
        self.timeout_minutes = timeout_minutes
        self.max_tokens = max_tokens

        # Azure config
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_api_version = azure_api_version or os.getenv("AZURE_OPENAI_API_VERSION")

        # Set up custom temp directory
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

        if not self.azure_endpoint:
            raise ValueError("Missing Azure endpoint. Set azure_endpoint or AZURE_OPENAI_ENDPOINT.")
        if not self.azure_api_version:
            raise ValueError("Missing Azure API version. Set azure_api_version or AZURE_OPENAI_API_VERSION.")

    @retry(
        (
            APITimeoutError,
            APIConnectionError,
            RateLimitError,
            InternalServerError,
            httpx.TimeoutException,
        ),
        tries=8,
        delay=1,
        backoff=2,
        logger=logger,
    )
    def get_ocr(self, file_for_ocr: str) -> dict:
        """
        Process an image file using OCR and return the extracted text (Azure OpenAI vision chat).
        """

        temp_file_for_ocr = None
        start_time = time.time()

        prompt_template = OCR_TO_MARKDOWN_PROMPT if self.markdown_output else OCR_TO_PLAIN_TEXT_PROMPT
        logger.info("Using prompt for %s format", "markdown" if self.markdown_output else "plain text")

        # Build Azure client
        azure_api_key = self.llm_api_key or os.getenv("AZURE_OPENAI_API_KEY")
        if not azure_api_key:
            raise ValueError("Missing Azure API key. Set llm_api_key or AZURE_OPENAI_API_KEY.")

        timeout_s = self.timeout_minutes * 60 if self.timeout_minutes is not None else None
        http_client = httpx.Client(timeout=timeout_s)

        client = AzureOpenAI(
            api_key=azure_api_key,
            azure_endpoint=self.azure_endpoint,
            api_version=self.azure_api_version,
            http_client=http_client,
        )

        try:
            mime_type, _ = mimetypes.guess_type(file_for_ocr)
            logger.info(f"OCR mime type: {mime_type}")

            file_size = os.path.getsize(file_for_ocr)
            logger.info(f"Initial image file size: {file_size}")

            # Compress/convert if too large or unsupported type
            if file_size > self.target_size * 1024 * 1024 or mime_type not in SUPPORTED_MIME_TYPES:
                logger.info(
                    f"Image exceeds {self.target_size}MB or unsupported mime type; compressing/converting"
                )
                temp_file_for_ocr = compress_and_convert_image(
                    input_path=file_for_ocr,
                    target_size=self.target_size,
                )
            else:
                logger.info("No compression/conversion needed")
                temp_file_for_ocr = file_for_ocr

            file_size = os.path.getsize(temp_file_for_ocr)
            logger.info(f"Final image file size: {file_size / (1024 * 1024):.2f} MB")

            # Azure vision chat expects either a public URL or base64 image data.
            # We'll use base64 data-URL.
            mime_type, _ = mimetypes.guess_type(temp_file_for_ocr)
            if mime_type is None:
                raise ValueError("Image format not recognized")

            with open(temp_file_for_ocr, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")

            data_url = f"data:{mime_type};base64,{image_b64}"

            # Chat completion with mixed content (text + image)
            response = client.chat.completions.create(
                model=self.ocr_model,  # Azure deployment name
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_template},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                temperature=0,
                max_tokens=self.max_tokens,
            )

            end_time = time.time()
            time_elapsed = end_time - start_time

            text_out = (response.choices[0].message.content or "").strip()

            prompt_tokens = getattr(response.usage, "prompt_tokens", 0) if response.usage else 0
            completion_tokens = getattr(response.usage, "completion_tokens", 0) if response.usage else 0

            logger.info(f"Completion tokens: {completion_tokens}")
            logger.info(f"Prompt tokens: {prompt_tokens}")

            final_ocr_dict = {
                "text": "" if "no readable text present" in text_out.lower() else text_out,
                "completion_tokens": completion_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_model": self.ocr_model,
                "completion_model_provider": self.ocr_model_provider,
                "text_chunks": "not provided",
            }

            logger.info(f"OCR performed using {self.ocr_model} in {time_elapsed:.2f} seconds")
            return final_ocr_dict

        finally:
            # Clean up the temporary compressed file (only if we created one)
            if temp_file_for_ocr and temp_file_for_ocr != file_for_ocr and os.path.exists(temp_file_for_ocr):
                os.remove(temp_file_for_ocr)