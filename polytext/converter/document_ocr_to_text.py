# converter/document_ocr_to_text.py
import os
import logging
import tempfile
import time
import mimetypes
from retry import retry
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

from ..prompts.ocr import (
    OCR_TO_MARKDOWN_NON_LITERAL_FALLBACK_PROMPT,
    OCR_TO_MARKDOWN_PROMPT,
    OCR_TO_PLAIN_TEXT_NON_LITERAL_FALLBACK_PROMPT,
    OCR_TO_PLAIN_TEXT_PROMPT,
    build_ocr_prompt,
)
from ..exceptions.base import EmptyDocument, ExceededMaxPages
from .gemini_quality_guards import (
    extract_finish_reason,
    tail_has_excessive_repetition,
)
from .image_preprocessing import (
    GEMINI_SUPPORTED_MIME_TYPES,
    convert_image_to_png,
    prepare_image_for_ocr,
)
from ..llm import LLMGenerationError, MultimodalLLM, normalize_provider

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = GEMINI_SUPPORTED_MIME_TYPES
OCR_MIN_OUTPUT_TOKENS = 500
OCR_MAX_OUTPUT_TOKENS = int(os.getenv("OCR_MAX_OUTPUT_TOKENS", "8192"))
OCR_TAIL_REPETITION_LINES = int(os.getenv("OCR_TAIL_REPETITION_LINES", "200"))
OCR_TAIL_REPETITION_THRESHOLD = float(os.getenv("OCR_TAIL_REPETITION_THRESHOLD", "0.35"))
OCR_FALLBACK_SOURCE_PATTERN = os.getenv("OCR_FALLBACK_SOURCE_PATTERN", "flash-lite-preview")
OCR_FALLBACK_MODEL = os.getenv("OCR_FALLBACK_MODEL", "gemini-3-flash-preview")
OCR_FALLBACK_TEMPERATURE = float(os.getenv("OCR_FALLBACK_TEMPERATURE", "1.0"))
OCR_FINAL_FALLBACK_MODEL = os.getenv("OCR_FINAL_FALLBACK_MODEL", "gemini-3.5-flash")
OCR_PROMPT_VARIANT_DEFAULT = "default"
OCR_PROMPT_VARIANT_NON_LITERAL_FALLBACK = "non_literal_fallback"
OCR_RETRIABLE_OUTPUT_ERROR_CODES = (993, 994, 996, 997, 999)
OPENAI_OUTPUT_ERROR_CODES = {
    "empty_response": 994,
    "content_filter": 993,
    "max_output_tokens": 999,
}


def compress_and_convert_image(input_path: str, target_size=1):
    """Backward-compatible wrapper around shared image conversion."""
    return convert_image_to_png(
        input_path,
        target_size_mb=target_size,
        mime_type=mimetypes.guess_type(input_path)[0],
    )

def get_document_ocr(
    document_for_ocr,
    markdown_output=False,
    llm_api_key=None,
    target_size=1,
    page_range=None,
    timeout_minutes=None,
    ocr_model: str | None = None,
    ocr_model_provider: str = "google",
    max_output_tokens: int | None = None,
    include_image_descriptions: bool = False,
    allow_partial_ocr_failures: bool = False,
):
    """
    Convenience function to extract text from an image file using OCR, optionally formatted as Markdown.

    This function initializes an `OCRToTextConverter` instance and uses it
    to extract text from the provided image file. The output can be formatted as
    Markdown or plain text based on the `markdown_output` parameter.

    Args:
        document_for_ocr (str): Path to the document file for OCR processing.
        markdown_output (bool, optional): If True, the extracted text will be
            formatted as Markdown. Defaults to False.
        llm_api_key (str, optional): API key for the LLM service. If provided,
            it will override the default configuration.
        target_size (int, optional): Gemini image conversion threshold in MB.
            Direct OpenAI uses resolution-aware preprocessing. Defaults to 1.
        page_range (tuple, optional): Optional page range to extract (start, end).
        timeout_minutes (int, optional): Number of minutes to wait for a response. Defaults to None.
        ocr_model (str | None, optional): OCR model to use. Defaults according to provider.
        ocr_model_provider (str, optional): Direct OCR provider ("google" or "openai").
            Defaults to "google".
        max_output_tokens (int | None, optional): Maximum output tokens.
            Defaults to the converter default.
        include_image_descriptions (bool, optional): If True, OCR prompts include
            brief functional descriptions for meaningful non-text images.
            Defaults to False.
        allow_partial_ocr_failures (bool, optional): If True, pages that still
            fail OCR after all retries are recorded inline instead of aborting
            the whole document extraction. Defaults to False.

    Returns:
        dict: Dictionary containing the OCR results and metadata.
    """
    resolved_provider = normalize_provider(ocr_model_provider)
    converter = DocumentOCRToTextConverter(
        ocr_model=ocr_model or (
            "gpt-5.6-luna" if resolved_provider == "openai" else "gemini-3.1-flash-lite"
        ),
        ocr_model_provider=resolved_provider,
        markdown_output=markdown_output,
        llm_api_key=llm_api_key,
        target_size=target_size,
        page_range=page_range,
        timeout_minutes=timeout_minutes,
        max_output_tokens=max_output_tokens,
        include_image_descriptions=include_image_descriptions,
        allow_partial_ocr_failures=allow_partial_ocr_failures,
    )
    return converter.get_document_ocr(document_for_ocr)

class DocumentOCRToTextConverter:
    def __init__(self, ocr_model="gemini-3.1-flash-lite", ocr_model_provider="google",
                markdown_output=True, llm_api_key=None, target_size=1, temp_dir="temp",
                 page_range=None, timeout_minutes: int = None, fallback_stage: int = 0,
                 max_output_tokens: int | None = None, include_image_descriptions: bool = False,
                 prompt_variant: str = OCR_PROMPT_VARIANT_DEFAULT,
                 allow_partial_ocr_failures: bool = False):
        """
        Initialize the DocumentOCRToTextConverter class with specified OCR model and formatting options.

        This class handles OCR processing of document pages using Google Gemini or
        the direct OpenAI Responses API.
        It supports various image formats and can output either plain text or markdown.

        Args:
            ocr_model (str): Model name for OCR processing. Defaults to "gemini-3.1-flash-lite".
            ocr_model_provider (str): Provider of OCR service. Defaults to "google".
            markdown_output (bool): Enable markdown formatting in output. Defaults to True.
            llm_api_key (str, optional): Override API key for language model. Defaults to None.
            target_size (int, optional): Gemini image conversion threshold in
                MB. Direct OpenAI uses resolution-aware preprocessing.
                Defaults to 1.
            temp_dir (str): Directory for temporary files. Defaults to "temp".
            page_range (tuple, optional): Optional page range to extract (start, end).
            timeout_minutes (int, optional): Number of minutes to wait for a response. Defaults to None.
            fallback_stage (int, optional): Internal retry stage used by fallback attempts.
                Defaults to 0.
            max_output_tokens (int | None, optional): Maximum output tokens.
                Defaults to `OCR_MAX_OUTPUT_TOKENS`.
            include_image_descriptions (bool, optional): If True, OCR prompts include
                brief functional descriptions for meaningful non-text images.
                Defaults to False.
            prompt_variant (str, optional): Prompt variant used by this attempt.
                Defaults to "default".
            allow_partial_ocr_failures (bool, optional): If True, pages that still
                fail OCR after all retries are recorded inline instead of aborting
                the whole document extraction. Defaults to False.

        Raises:
            OSError: If temp directory creation fails
            ValueError: If invalid model or provider specified
        """
        self.ocr_model = ocr_model
        self.ocr_model_provider = normalize_provider(ocr_model_provider)
        self.markdown_output = markdown_output
        self.llm_api_key = llm_api_key
        self.target_size = target_size
        self.page_range = page_range
        self.timeout_minutes = timeout_minutes
        self.include_image_descriptions = include_image_descriptions
        self.prompt_variant = prompt_variant
        self.allow_partial_ocr_failures = allow_partial_ocr_failures
        requested_output_tokens = OCR_MAX_OUTPUT_TOKENS if max_output_tokens is None else max_output_tokens
        self.max_output_tokens = max(requested_output_tokens, OCR_MIN_OUTPUT_TOKENS)
        self.fallback_stage = fallback_stage
        self.fallback_source_pattern = OCR_FALLBACK_SOURCE_PATTERN
        self.fallback_model = (
            os.getenv("OPENAI_OCR_FALLBACK_MODEL", "gpt-5.6-terra")
            if self.ocr_model_provider == "openai"
            else OCR_FALLBACK_MODEL
        )
        self.fallback_temperature = OCR_FALLBACK_TEMPERATURE
        self.final_fallback_model = (
            os.getenv("OPENAI_OCR_FINAL_FALLBACK_MODEL") or None
            if self.ocr_model_provider == "openai"
            else OCR_FINAL_FALLBACK_MODEL
        )

        # Set up custom temp directory
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

    def _build_prompt_template(self) -> str:
        if self.markdown_output and self.prompt_variant == OCR_PROMPT_VARIANT_NON_LITERAL_FALLBACK:
            base_prompt = OCR_TO_MARKDOWN_NON_LITERAL_FALLBACK_PROMPT
        elif not self.markdown_output and self.prompt_variant == OCR_PROMPT_VARIANT_NON_LITERAL_FALLBACK:
            base_prompt = OCR_TO_PLAIN_TEXT_NON_LITERAL_FALLBACK_PROMPT
        elif self.markdown_output:
            base_prompt = OCR_TO_MARKDOWN_PROMPT
        else:
            base_prompt = OCR_TO_PLAIN_TEXT_PROMPT
        return build_ocr_prompt(
            base_prompt,
            include_image_descriptions=self.include_image_descriptions,
        )

    def should_prompt_fallback_retry(self, error: EmptyDocument) -> bool:
        if self.fallback_stage != 0:
            return False
        if self.prompt_variant == OCR_PROMPT_VARIANT_NON_LITERAL_FALLBACK:
            return False
        return error.code in OCR_RETRIABLE_OUTPUT_ERROR_CODES

    def should_fallback_temperature_retry(self, error: EmptyDocument, temperature: float) -> bool:
        expected_stage = 1 if self.markdown_output else 0
        if self.fallback_stage != expected_stage:
            return False
        if error.code not in OCR_RETRIABLE_OUTPUT_ERROR_CODES:
            return False
        if self.fallback_model == self.ocr_model and temperature == self.fallback_temperature:
            return False
        if self.fallback_source_pattern and self.fallback_source_pattern in self.ocr_model:
            return True
        return self.ocr_model != self.fallback_model

    def should_final_fallback_model(self, error: EmptyDocument) -> bool:
        expected_stage = 2 if self.markdown_output else 1
        if self.fallback_stage != expected_stage:
            return False
        if error.code not in OCR_RETRIABLE_OUTPUT_ERROR_CODES:
            return False
        if not self.final_fallback_model or self.final_fallback_model == self.ocr_model:
            return False
        return self.ocr_model == self.fallback_model

    def run_fallback(
        self,
        file_for_ocr: str,
        reason: str,
        fallback_model: str,
        fallback_temperature: float,
        fallback_stage: int,
        prompt_variant: str | None = None,
    ) -> dict:
        resolved_prompt_variant = prompt_variant or self.prompt_variant
        logger.info(
            "Retrying document OCR with fallback model %s, prompt variant %s and temperature %s for %s because %s",
            fallback_model,
            resolved_prompt_variant,
            fallback_temperature,
            file_for_ocr,
            reason,
        )
        fallback_converter = DocumentOCRToTextConverter(
            ocr_model=fallback_model,
            ocr_model_provider=self.ocr_model_provider,
            markdown_output=self.markdown_output,
            llm_api_key=self.llm_api_key,
            target_size=self.target_size,
            temp_dir=self.temp_dir,
            page_range=self.page_range,
            timeout_minutes=self.timeout_minutes,
            fallback_stage=fallback_stage,
            max_output_tokens=self.max_output_tokens,
            include_image_descriptions=self.include_image_descriptions,
            prompt_variant=resolved_prompt_variant,
            allow_partial_ocr_failures=self.allow_partial_ocr_failures,
        )
        result = fallback_converter.get_ocr(
            file_for_ocr=file_for_ocr,
            temperature=fallback_temperature,
        )
        result.setdefault("fallback_from_model", self.ocr_model)
        result.setdefault("fallback_to_model", fallback_model)
        result.setdefault("fallback_reason", reason)
        result.setdefault("fallback_temperature", fallback_temperature)
        result.setdefault("fallback_from_prompt_variant", self.prompt_variant)
        result.setdefault("fallback_to_prompt_variant", resolved_prompt_variant)
        return result

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
    def get_ocr(self, file_for_ocr, temperature: float = 0.0):
        """
        Process an image file using OCR and return the extracted text.

        This method handles image compression/conversion if needed and uses
        the configured vision API to extract and format the text content.

        Args:
            file_for_ocr (str): Path to the image file for OCR processing.
            temperature (float, optional): Temperature used for this OCR attempt.
                Defaults to 0.0.

        Returns:
            dict: Dictionary containing:
                - text (str): The extracted text
                - completion_tokens (int): Number of tokens in completion
                - prompt_tokens (int): Number of tokens in prompt
                - completion_model (str): Name of the model used
                - completion_model_provider (str): Provider of the OCR service
                - finish_reason (str | None): Provider finish reason for the attempt
                - max_output_tokens (int): Maximum output tokens configured for the attempt
                - temperature (float): Temperature used for the attempt

        Raises:
            ValueError: If the image file format is not recognized
            Exception: For errors during OCR processing
        """
        temp_file_for_ocr = None
        should_delete_temp_file = False
        start_time = time.time()

        if self.markdown_output:
            logger.info("Using prompt for markdown format")
        else:
            logger.info("Using prompt for plain text format")
        prompt_template = self._build_prompt_template()

        try:
            client = None
            config = None
            if self.ocr_model_provider == "google":
                if self.llm_api_key:
                    logger.info("Using provided Google API key")
                    client = genai.Client(api_key=self.llm_api_key)
                else:
                    logger.info("Using Google API key from ENV")
                    client = genai.Client()

                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=self.max_output_tokens,
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
                    http_options=(
                        types.HttpOptions(timeout=self.timeout_minutes * 60_000)
                        if self.timeout_minutes is not None else None
                    ),
                    system_instruction=[prompt_template]
                )

            prepared_image = prepare_image_for_ocr(
                file_for_ocr,
                provider=self.ocr_model_provider,
                target_size_mb=self.target_size,
            )
            temp_file_for_ocr = prepared_image.path
            should_delete_temp_file = prepared_image.is_temporary
            file_size = prepared_image.file_size
            mime_type = prepared_image.mime_type
            logger.info(f"OCR mime type: {mime_type}")

            logger.info(f"Final image file size: {file_size / (1024 * 1024):.2f} MB")

            if self.ocr_model_provider == "openai":
                with open(temp_file_for_ocr, "rb") as image_file:
                    image_data = image_file.read()
                mime_type, _ = mimetypes.guess_type(temp_file_for_ocr)
                if mime_type is None:
                    raise ValueError("Image format not recognized")
                try:
                    generation = MultimodalLLM(
                        model=self.ocr_model,
                        provider=self.ocr_model_provider,
                        api_key=self.llm_api_key,
                        timeout_minutes=self.timeout_minutes,
                    ).generate_text_from_image(
                        instructions=prompt_template,
                        image_data=image_data,
                        mime_type=mime_type,
                        max_output_tokens=self.max_output_tokens,
                        temperature=temperature,
                    )
                except LLMGenerationError as error:
                    error_code = OPENAI_OUTPUT_ERROR_CODES.get(error.reason)
                    if error_code is None:
                        raise
                    logger.warning(
                        "OpenAI document OCR returned unusable output for %s: model=%s reason=%s prompt_tokens=%s completion_tokens=%s partial_output=%r",
                        file_for_ocr,
                        self.ocr_model,
                        error.reason,
                        error.prompt_tokens,
                        error.completion_tokens,
                        error.partial_text,
                    )
                    raise EmptyDocument(
                        message=f"OpenAI document OCR returned unusable output ({error.reason}) for image: {file_for_ocr}",
                        code=error_code,
                    ) from error
                response_text = generation.text
                finish_reason = generation.finish_reason
                completion_tokens = generation.completion_tokens
                prompt_tokens = generation.prompt_tokens
            elif file_size > 20 * 1024 * 1024:
                logger.info("Total image file size exceeds 20MB, uploading file before transcription")

                myfile = client.files.upload(file=temp_file_for_ocr)

                logger.info(f"Uploaded image file - Starting OCR...")

                contents = [myfile]
                response = client.models.generate_content(
                    model=self.ocr_model,
                    contents=contents,
                    config=config
                )

                response_text = response.text or ""
                finish_reason = extract_finish_reason(response)
                completion_tokens = response.usage_metadata.candidates_token_count
                prompt_tokens = response.usage_metadata.prompt_token_count

                client.files.delete(name=myfile.name)

            else:
                logger.info("Image file size does not exceed 20MB")
                with open(temp_file_for_ocr, "rb") as f:
                    image_data = f.read()

                # Determine mimetype
                mime_type, _ = mimetypes.guess_type(temp_file_for_ocr)
                if mime_type is None:
                    try:
                        raise ValueError("Image format not recognized")
                    except ValueError:
                        logger.exception("Unsupported image format for %s", temp_file_for_ocr)
                        raise

                response = client.models.generate_content(
                    model=self.ocr_model,
                    contents=[
                        types.Part.from_bytes(
                            data=image_data,
                            mime_type=mime_type,
                        )
                    ],
                    config=config
                )

                response_text = response.text or ""
                finish_reason = extract_finish_reason(response)
                completion_tokens = response.usage_metadata.candidates_token_count
                prompt_tokens = response.usage_metadata.prompt_token_count

            end_time = time.time()
            time_elapsed = end_time - start_time
            has_repetitive_tail = tail_has_excessive_repetition(
                response_text,
                tail_lines=OCR_TAIL_REPETITION_LINES,
                threshold=OCR_TAIL_REPETITION_THRESHOLD,
            )

            logger.info(f"Completion tokens: {completion_tokens}")
            logger.info(f"Prompt tokens: {prompt_tokens}")

            if self.ocr_model_provider == "google" and finish_reason and "RECITATION" in finish_reason:
                raise EmptyDocument(
                    message=f"Document OCR blocked because recitation was detected for image: {file_for_ocr}",
                    code=996,
                )

            if self.ocr_model_provider == "google" and finish_reason and "MAX_TOKENS" in finish_reason:
                raise EmptyDocument(
                    message=f"Document OCR truncated because max output tokens were reached for image: {file_for_ocr}",
                    code=999,
                )

            if has_repetitive_tail:
                logger.warning(
                    "Document OCR repetitive output for %s: model=%s provider=%s output=%r",
                    file_for_ocr,
                    self.ocr_model,
                    self.ocr_model_provider,
                    response_text,
                )
                raise EmptyDocument(
                    message=f"Document OCR discarded because repetitive tail was detected for image: {file_for_ocr}",
                    code=997,
                )

            final_ocr_dict = {
                "text": response_text if "no readable text present" not in response_text.lower() else "",
                "completion_tokens": completion_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_model": self.ocr_model,
                "completion_model_provider": self.ocr_model_provider,
                "text_chunks": "not provided",
                "finish_reason": finish_reason,
                "max_output_tokens": self.max_output_tokens,
                "temperature": temperature,
                "prompt_variant": self.prompt_variant,
            }

            logger.info(f"OCR performed using {self.ocr_model} in {time_elapsed:.2f} seconds")
            return final_ocr_dict
        except EmptyDocument as e:
            if self.should_prompt_fallback_retry(e):
                return self.run_fallback(
                    file_for_ocr=file_for_ocr,
                    reason=e.message,
                    fallback_model=self.ocr_model,
                    fallback_temperature=temperature,
                    fallback_stage=1,
                    prompt_variant=OCR_PROMPT_VARIANT_NON_LITERAL_FALLBACK,
                )
            if self.should_fallback_temperature_retry(e, temperature):
                return self.run_fallback(
                    file_for_ocr=file_for_ocr,
                    reason=e.message,
                    fallback_model=self.fallback_model,
                    fallback_temperature=self.fallback_temperature,
                    fallback_stage=2 if self.markdown_output else 1,
                )
            if self.should_final_fallback_model(e):
                return self.run_fallback(
                    file_for_ocr=file_for_ocr,
                    reason=e.message,
                    fallback_model=self.final_fallback_model,
                    fallback_temperature=0.0,
                    fallback_stage=3 if self.markdown_output else 2,
                )
            raise

        finally:
            if should_delete_temp_file and temp_file_for_ocr and os.path.exists(temp_file_for_ocr):
                os.remove(temp_file_for_ocr)

    def get_document_ocr(self, document_for_ocr):
        """
        Extract text from a document using OCR with parallel processing.

        Args:
            document_for_ocr (str): Path to the document file for OCR processing.

        Returns:
            dict: Dictionary containing the OCR results and metadata.
                The per-page OCR attempts may include fallback metadata when a page
                is retried with a fallback model.
        """
        import fitz
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def process_page(page_tuple):
            page_num, page = page_tuple
            fd, temp_image_path = tempfile.mkstemp(suffix='.png')
            os.close(fd)

            try:
                # Convert page to image
                pix = page.get_pixmap()
                pix.save(temp_image_path)

                # Perform OCR on the page
                try:
                    ocr_result = self.get_ocr(temp_image_path)
                except (EmptyDocument, LLMGenerationError) as error:
                    if not self.allow_partial_ocr_failures:
                        raise
                    error_message = getattr(error, "message", str(error))
                    logger.warning(
                        "Document OCR failed on page %s after retries; keeping partial document because allow_partial_ocr_failures=True: %s",
                        page_num + 1,
                        error_message,
                    )
                    ocr_result = {
                        "text": "",
                        "completion_tokens": 0,
                        "prompt_tokens": 0,
                        "completion_model": self.ocr_model,
                        "completion_model_provider": self.ocr_model_provider,
                        "text_chunks": "not provided",
                        "page_error": True,
                        "page_error_reason": error_message,
                    }
                return page_num, ocr_result

            finally:
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)

        try:
            pdf = fitz.open(document_for_ocr)
            start_page, end_page = self.validate_page_range(len(pdf))

            # Create list of (page_num, page) tuples to process
            pages_to_process = [(i, pdf[i]) for i in range(start_page, end_page)]
            results = []

            # Process pages in parallel
            with ThreadPoolExecutor() as executor:
                future_to_page = {
                    executor.submit(process_page, page_tuple): page_tuple[0]
                    for page_tuple in pages_to_process
                }

                for future in as_completed(future_to_page):
                    page_num, result = future.result()
                    results.append((page_num, result))

            # Sort results by page number
            results.sort(key=lambda x: x[0])

            # Combine results
            all_text = []
            total_completion_tokens = 0
            total_prompt_tokens = 0
            failed_pages = []

            for page_num, ocr_result in results:
                all_text.append(f"{ocr_result['text']}\n")
                total_completion_tokens += ocr_result['completion_tokens']
                total_prompt_tokens += ocr_result['prompt_tokens']
                if ocr_result.get("page_error"):
                    failed_pages.append({
                        "page": page_num + 1,
                        "reason": ocr_result.get("page_error_reason", "unknown"),
                    })

            pdf.close()

            final_result_dict = {
                "text": "\n".join(all_text),
                "completion_tokens": total_completion_tokens,
                "prompt_tokens": total_prompt_tokens,
                "completion_model": self.ocr_model,
                "completion_model_provider": self.ocr_model_provider,
                "text_chunks": "not provided",
                "ocr_failed_pages": [item["page"] for item in failed_pages],
                "ocr_failed_pages_detail": failed_pages,
            }

            return final_result_dict

        except Exception as e:
            logger.info(f"Error processing document: {e}")
            raise

    def validate_page_range(self, total_pages: int) -> tuple[int, int]:
        """
        Validate and normalize page range for text extraction.

        Converts 1-indexed page numbers (user input) to 0-indexed (internal)
        and validates against document bounds.

        Args:
            total_pages: Total number of pages in document

        Returns:
            Tuple of (start_page, end_page) normalized to 0-indexed values

        Raises:
            ExceededMaxPages: If page range exceeds document length or starts at 0
        """
        if self.page_range:
            logger.info(f"Using page range: {self.page_range[0]} - {self.page_range[1]}")
            if self.page_range[1] > total_pages or self.page_range[0] < 1:
                raise ExceededMaxPages(
                    message=f"Requested page range {self.page_range} exceeds document length ({total_pages})",
                    code=998
                )
            start_page = max(0, self.page_range[0] - 1)  # Convert to 0-indexed
            end_page = min(self.page_range[1], total_pages)
        else:
            start_page = 0
            end_page = total_pages

        return start_page, end_page
