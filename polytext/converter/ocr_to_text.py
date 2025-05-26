# converter/ocr_to_text.py
import os
import logging
import tempfile
import time
import mimetypes
import ffmpeg
from retry import retry
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

from ..prompts.ocr import OCR_TO_MARKDOWN_PROMPT, OCR_TO_PLAIN_TEXT_PROMPT

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/webp', 'image/heic', 'image/heif',
}


def compress_and_convert_image(input_path: str, target_size=1):
    """
    Compress and convert image files to PNG format using ffmpeg.

    Args:
        input_path (str): Path to the original image file
        target_size (int, optional): Target file size in bytes. Defaults to 1MB

    Returns:
        str: Path to the temporary compressed/converted PNG file

    Raises:
        RuntimeError: If FFmpeg compression/conversion fails

    Notes:
        - Creates a temporary PNG file that should be deleted after use
        - Compresses images over target_size
        - Uses maximum available CPU threads for faster processing
    """
    target_size = target_size * 1024 * 1024
    temp_dir = os.path.abspath("temp")
    os.makedirs(temp_dir, exist_ok=True)
    tempfile.tempdir = temp_dir
    try:
        # Create temporary file for image output
        fd, temp_image_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)

        # Get original file size
        original_size = os.path.getsize(input_path)
        logger.info(f"Original image size: {original_size / 1024 / 1024:.2f}MB")

        if original_size > target_size:
            # Calculate compression ratio based on target size
            compression_ratio = (target_size / original_size) ** 0.5
            new_size = int(100 * compression_ratio)  # Convert to percentage
            new_size = max(1, min(new_size, 100))  # Ensure between 1-100

            logger.info(f"Compressing image to {new_size}% quality")
            ffmpeg.input(input_path).output(
                temp_image_path,
                vf=f'scale=iw*{compression_ratio}:ih*{compression_ratio}',  # Scale dimensions
                compression_level=9,  # Maximum PNG compression
                threads=0,  # Use maximum available threads
                loglevel='error'  # Reduce logging overhead
            ).run(quiet=True, overwrite_output=True)
        else:
            # Just convert to PNG if no compression needed
            logger.info("Converting image to PNG without compression")
            ffmpeg.input(input_path).output(
                temp_image_path,
                compression_level=9,
                threads=0,
                loglevel='error'
            ).run(quiet=True, overwrite_output=True)

        logger.info(f"Successfully processed image: {temp_image_path}")
        return temp_image_path

    except Exception as e:
        raise RuntimeError(f"FFmpeg error during image processing: {e}") from e

def get_ocr(file_for_ocr, markdown_output=False, llm_api_key=None, target_size=1):
    """
    Convenience function to extract text from an image file using OCR, optionally formatted as Markdown.

    This function initializes an `OCRToTextConverter` instance and uses it
    to extract text from the provided image file. The output can be formatted as
    Markdown or plain text based on the `markdown_output` parameter.

    Args:
        file_for_ocr (str): Path to the image file for OCR processing.
        markdown_output (bool, optional): If True, the extracted text will be
            formatted as Markdown. Defaults to False.
        llm_api_key (str, optional): API key for the LLM service. If provided,
            it will override the default configuration.
        target_size (int, optional): Target file size in bytes. Defaults to 1MB

    Returns:
        dict: Dictionary containing the OCR results and metadata.
    """
    converter = OCRToTextConverter(markdown_output=markdown_output, llm_api_key=llm_api_key, target_size=target_size)
    return converter.get_ocr(file_for_ocr)

class OCRToTextConverter:
    def __init__(self, ocr_model="gemini-2.0-flash", ocr_model_provider="google",
                markdown_output=True, llm_api_key=None, target_size=1, temp_dir="temp"):
        """
        Initialize the OCRToTextConverter class with specified OCR model and formatting options.

        This class handles OCR processing of images using Google's Gemini Vision API.
        It supports various image formats and can output either plain text or markdown.

        Args:
            ocr_model (str): Model name for OCR processing. Defaults to "gemini-2.0-flash".
            ocr_model_provider (str): Provider of OCR service. Defaults to "google".
            markdown_output (bool): Enable markdown formatting in output. Defaults to True.
            llm_api_key (str, optional): Override API key for language model. Defaults to None.
            target_size (int, optional): Target file size in bytes. Defaults to 1MB
            temp_dir (str): Directory for temporary files. Defaults to "temp".

        Raises:
            OSError: If temp directory creation fails
            ValueError: If invalid model or provider specified
        """
        self.ocr_model = ocr_model
        self.ocr_model_provider = ocr_model_provider
        self.markdown_output = markdown_output
        self.llm_api_key = llm_api_key
        self.target_size = target_size

        # Set up custom temp directory
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

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
    def get_ocr(self, file_for_ocr):
        """
        Process an image file using OCR and return the extracted text.

        This method handles image compression/conversion if needed and uses
        Google's Gemini Vision API to extract and format the text content.

        Args:
            file_for_ocr (str): Path to the image file for OCR processing.

        Returns:
            dict: Dictionary containing:
                - text (str): The extracted text
                - completion_tokens (int): Number of tokens in completion
                - prompt_tokens (int): Number of tokens in prompt
                - completion_model (str): Name of the model used
                - completion_model_provider (str): Provider of the OCR service

        Raises:
            ValueError: If the image file format is not recognized
            Exception: For errors during OCR processing
        """

        temp_file_for_ocr = None
        start_time = time.time()

        if self.markdown_output:
            logger.info("Using prompt for markdown format")
            # Convert the text to markdown format
            prompt_template = OCR_TO_MARKDOWN_PROMPT
        else:
            logger.info("Using prompt for plain text format")
            # Convert the text to plain text format
            prompt_template = OCR_TO_PLAIN_TEXT_PROMPT

        try:
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
                ]
            )

            mime_type, _ = mimetypes.guess_type(file_for_ocr)
            logger.info(f"OCR mime type: {mime_type}")
            file_size = os.path.getsize(file_for_ocr)
            logger.info(f"Initial image file size: {file_size}")
            if file_size > self.target_size * 1024 * 1024 or mime_type not in SUPPORTED_MIME_TYPES:
                logger.info(f"Image file size exceeds {self.target_size}MB or unsupported mime type, compressing and converting image")
                temp_file_for_ocr = compress_and_convert_image(input_path=file_for_ocr, target_size=self.target_size)
                file_size = os.path.getsize(temp_file_for_ocr)
            else:
                logger.info(f"Image file size does not exceed {self.target_size}MB and mime type is supported, no compression or conversion needed")
                temp_file_for_ocr = file_for_ocr

            logger.info(f"Final image file size: {file_size / (1024 * 1024):.2f} MB")

            if file_size > 20 * 1024 * 1024:
                logger.info("Total image file size exceeds 20MB, uploading file before transcription")

                myfile = client.files.upload(file=temp_file_for_ocr)

                logger.info(f"Uploaded image file - Starting OCR...")

                contents = [prompt_template, myfile]
                response = client.models.generate_content(
                    model=self.ocr_model,
                    contents=contents,
                    config=config
                )

                client.files.delete(name=myfile.name)

            else:
                logger.info("Image file size does not exceed 20MB")
                with open(temp_file_for_ocr, "rb") as f:
                    image_data = f.read()

                # Determine mimetype
                mime_type, _ = mimetypes.guess_type(temp_file_for_ocr)
                if mime_type is None:
                    raise ValueError("Image format not recognized")

                response = client.models.generate_content(
                    model=self.ocr_model,
                    contents=[
                        prompt_template,
                        types.Part.from_bytes(
                            data=image_data,
                            mime_type=mime_type,
                        )
                    ],
                    config=config
                )

            end_time = time.time()
            time_elapsed = end_time - start_time

            logger.info(f"Completion tokens: {response.usage_metadata.candidates_token_count}")
            logger.info(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")

            final_ocr_dict = {
                "text": response.text,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_model": self.ocr_model,
                "completion_model_provider": self.ocr_model_provider
            }

            logger.info(f"OCR performed using {self.ocr_model} in {time_elapsed:.2f} seconds")
            return final_ocr_dict

        finally:
            # Clean up the temporary compressed file
            if temp_file_for_ocr and os.path.exists(temp_file_for_ocr):
                os.remove(temp_file_for_ocr)

