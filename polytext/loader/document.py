# document.py
# Standard library imports
import os
import re
import tempfile
import logging
import concurrent.futures
from collections import Counter
from pymupdf4llm import to_markdown
from markitdown import MarkItDown

# Third-party imports
from pypdf import PdfReader
import fitz  # PyMuPDF
from botocore.exceptions import ClientError

# Local imports
from ..converter.pdf import convert_to_pdf
from ..exceptions.base import EmptyDocument, ExceededMaxPages, LoaderError
from ..loader.downloader.downloader import Downloader

logger = logging.getLogger(__name__)

MIN_DOC_TEXT_LENGHT_ACCEPTED = int(os.getenv("MIN_DOC_TEXT_LENGHT_ACCEPTED", "400"))

class DocumentLoader:
    """
    Loads and extracts text from documents with support for cloud storage (S3 or GCS).

    Handles document downloading, format conversion to PDF using LibreOffice,
    and text extraction using PyMuPDF or PyPDF backends. Supports quality checks
    and validation of extracted content.

    Attributes:
        source (str): Source type ("cloud" or "local")
        markdown_output (bool): Whether to format output as markdown
        s3_client: Boto3 S3 client for AWS operations
        document_aws_bucket (str): Default S3 bucket name
        gcs_client: Google Cloud Storage client
        document_gcs_bucket (str): Default GCS bucket name
        type (str): Content type identifier ("document")
        page_range (tuple): Optional page range to extract (start, end)
        temp_dir (str): Directory for temporary files
    """

    def __init__(self, source: str, markdown_output: bool = True, s3_client: object = None,
                 document_aws_bucket: str = None, gcs_client: object = None,
                 document_gcs_bucket: str = None, temp_dir: str = 'temp',
                 page_range: tuple[int, int] = None, timeout_minutes: int = None, **kwargs) -> None:
        """
        Initialize DocumentLoader with optional cloud storage configuration.

        Args:
            source (str): Source type for documents ("cloud" or "local")
            markdown_output (bool): Whether to format output as markdown (default: True)
            s3_client (object): Boto3 S3 client instance for AWS operations (optional)
            document_aws_bucket (str): Default S3 bucket name for storage (optional)
            gcs_client (object): Google Cloud Storage client instance (optional)
            document_gcs_bucket (str): Default GCS bucket name for storage (optional)
            temp_dir (str): Directory for temporary files (default: 'temp')
            page_range (tuple): Optional page range to extract (start, end)
            timeout (int): Timeout for converting to markdown (default: None)

        Raises:
            ValueError: If source is not "cloud" or "local"
            AttributeError: If no storage client is provided for cloud source
        """
        self.source = source
        self.markdown_output = markdown_output
        self.s3_client = s3_client
        self.document_aws_bucket = document_aws_bucket
        self.gcs_client = gcs_client
        self.document_gcs_bucket = document_gcs_bucket
        self.type = "document"
        self.page_range = page_range
        self.timeout_minutes = timeout_minutes

        # Set up custom temp directory
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

    def download_document(self, file_path: str, temp_file_path: str) -> str:
        """
        Download a document file from cloud storage (S3 or GCS) to a local path.

        First attempts to download with original extension, then tries uppercase.
        If both fail, converts the document using LibreOffice. Supports downloading
        from either S3 or GCS based on configured client.

        Args:
            file_path (str): Cloud storage path (s3:// or gcs:// URI format)
            temp_file_path (str): Local filesystem path to save downloaded file

        Returns:
            str: Path to downloaded file, potentially converted to PDF

        Raises:
            ClientError: If cloud storage operations fail
            AttributeError: If no storage client is configured
            ConversionError: If document conversion fails
        """
        if self.s3_client is not None:
            try:
                downloader = Downloader(s3_client=self.s3_client, document_aws_bucket=self.document_aws_bucket)
                downloader.download_file_from_s3(file_path, temp_file_path)
                logger.info(f'Downloaded {file_path} to {temp_file_path}')
            except ClientError as e:
                logger.info(e)
                self.s3_client.download_file(Bucket=self.document_aws_bucket,
                                             Key=file_path.replace(".pdf", ".PDF"),
                                             Filename=temp_file_path)
            return temp_file_path
        elif self.gcs_client is not None:
            try:
                downloader = Downloader(gcs_client=self.gcs_client, document_gcs_bucket=self.document_gcs_bucket)
                downloader.download_file_from_gcs(file_path, temp_file_path)
                logger.info(f'Downloaded {file_path} to {temp_file_path}')
            except ClientError as e:
                logger.info(e)
                bucket = self.gcs_client.bucket(self.document_gcs_bucket)
                blob = bucket.blob(file_path.replace(".pdf", ".PDF"))
                # Download file
                blob.download_to_filename(temp_file_path)
            return temp_file_path
        raise AttributeError('Storage client not provided')

    def convert_doc_to_pdf(self, file_prefix: str, input_file: str) -> str:
        """
        Convert any document format to PDF using cloud storage and LibreOffice.

        Downloads the document from S3 or GCS using file_prefix to locate it,
        saves it locally to input_file path, and converts to PDF using LibreOffice.
        Handles cleanup of temporary files.

        Args:
            file_prefix (str): Full cloud storage path (s3:// or gcs:// URI)
            input_file (str): Temporary local path to save downloaded file

        Returns:
            str: Path to the generated PDF file in temporary directory

        Raises:
            FileNotFoundError: If no matching document found in cloud storage
            ConversionError: If LibreOffice conversion fails
            AttributeError: If neither S3 nor GCS client is configured
            ClientError: If cloud storage operations fail
        """
        logger.info(f"file_prefix: {file_prefix}")
        logger.info(f"input_file: {input_file}")

        # Create a temporary file for output
        fd, output_file = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)  # Close file descriptor explicitly

        logger.info("Using LibreOffice")
        convert_to_pdf(input_file=input_file, output_file=output_file, original_file=file_prefix)
        logger.info(f"Document converted to pdf and saved to {output_file}")
        os.remove(input_file)
        return output_file

    # PDF text extraction methods

    def get_document_text(self, file_path: str) -> dict:
        """
        Extract text from a document using PyMuPDF.

        Downloads the document if using cloud storage, converts to PDF if needed,
        and extracts text with quality checks. Uses multi-stage validation to ensure
        text quality.

        Args:
            file_path: Path to document file (local path or cloud URI)

        Returns:
            Dictionary containing:
                - text: Extracted document text
                - completion_tokens: Number of completion tokens (0)
                - prompt_tokens: Number of prompt tokens (0)
                - completion_model: Model name ("not provided")
                - completion_model_provider: Model provider ("not provided")
                - text_chunks: Text chunks ("not provided")
                - type: Document type ("document")
                - input: Original file path

        Raises:
            EmptyDocument: If extracted text is empty or fails quality checks
            ExceededMaxPages: If requested page range is invalid
            ValueError: If source is not "cloud" or "local"
        """
        logger.debug("Using PyMuPDF")

        if self.source == "cloud":
            fd, temp_file_path = tempfile.mkstemp()
            try:
                temp_file_path = self.download_document(file_path, temp_file_path)
                logger.info(f"Successfully loaded document from {file_path}")
            finally:
                os.close(fd)
        elif self.source == "local":
            temp_file_path = file_path
            logger.info(f"Successfully loaded document from local path {file_path}")
        else:
            raise ValueError("Invalid OCR source. Choose 'cloud' or 'local'.")

        # Handle PDF conversion and opening
        if os.path.splitext(file_path)[1].lower() != ".pdf":
            logger.info("Converting file to PDF")
            file_prefix = file_path
            temp_file_path = self.convert_doc_to_pdf(file_prefix=file_prefix, input_file=temp_file_path)
            pdf_document = fitz.open(temp_file_path)
        else:
            try:
                pdf_document = fitz.open(temp_file_path)
                logger.info(f"Successfully opened file with temp_file_path: {temp_file_path}")
            except Exception as e:
                logger.info("Converting file to PDF")
                file_prefix = file_path
                temp_file_path = self.convert_doc_to_pdf(file_prefix=file_prefix, input_file=temp_file_path)
                pdf_document = fitz.open(temp_file_path)

        total_pages = pdf_document.page_count
        logger.info(f"Total pages: {total_pages}")

        # Validate and adjust page range
        start_page, end_page = self.validate_page_range(total_pages)

        try_not_markdown = True
        if self.markdown_output:
            # Use pymupdf4llm for markdown conversion
            logger.info("Converting file to Markdown")

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(to_markdown, pdf_document, pages=list(range(start_page, end_page)))
            try:
                import time
                logger.info(f"Timeout_minutes: {self.timeout_minutes}")
                start = time.time()
                text = future.result(timeout=self.timeout_minutes * 60 if self.timeout_minutes else None)
                end = time.time()
                logger.info(f"Time elapsed: {end - start}")
                logger.info(f"Successfully converted {len(text)} pages to Markdown")

                if len(text) >= MIN_DOC_TEXT_LENGHT_ACCEPTED:
                    logger.info(f"Successfully converted {len(text)} text to Markdown")
                    try_not_markdown = False

            except concurrent.futures.TimeoutError:
                logger.info(f"Markdown conversion timed out after {self.timeout_minutes} minutes")
                try_not_markdown = True
                future.cancel()  # will only cancel if it hasn’t started
                executor.shutdown(wait=False, cancel_futures=True)
                executor = None  # avoid shutting down twice
            except Exception as e:
                logger.info(f"Markdown conversion failed: {e}")
                try_not_markdown = True
            finally:
                if executor is not None:
                    executor.shutdown(wait=True)

        if try_not_markdown:
            # Original plain text extraction
            logger.info("Not converting file to Markdown")
            text = ""
            last_pages_text = ""
            last_page_index_to_start = 10

            try:
                for page_number in range(start_page, end_page):
                    page = pdf_document.load_page(page_number)
                    page_text = page.get_text("text", flags=16)
                    page_text = self.clean_text(page_text)
                    text += page_text
                    if page_number >= (pdf_document.page_count - last_page_index_to_start):
                        last_pages_text += page_text

                    # Early termination checks
                    if len(text) == 0 and page_number == 10:
                        message = "First 10 pages of the document are empty"
                        logger.info(message)
                        raise EmptyDocument(message=message, code=998)

                    if len(text) < MIN_DOC_TEXT_LENGHT_ACCEPTED and page_number == 20:
                        message = f"First 20 pages of the document have less than {MIN_DOC_TEXT_LENGHT_ACCEPTED} chars"
                        logger.info(message)
                        raise EmptyDocument(message=message, code=998)

                    if (total_pages >= 500 and
                            page_number == 10 and
                            self.has_repeated_rows(text=text, threshold=100)):
                        message = "First 10 pages of the document have 100 repeated rows"
                        logger.info(message)
                        raise EmptyDocument(message=message, code=998)

                    if (total_pages >= 500 and
                            (page_number == total_pages - 1) and
                            self.has_repeated_rows(text=last_pages_text, threshold=100)):
                        message = "Last 10 pages of the document have 100 repeated rows"
                        logger.info(message)
                        raise EmptyDocument(message=message, code=998)
            except EmptyDocument as e:
                raise e
            except Exception as e:
                logger.info(f"Error during text extraction: {e}")
                raise LoaderError(message="text extraction error", status=422, code="TEXT EXTRACTION ERROR")


        pdf_document.close()
        if self.source == "cloud":
            os.remove(temp_file_path)

        if len(text) == 0:
            message = "No text detected"
            logger.info(message)
            raise EmptyDocument(message=message, code=998)

        if "������������������������������������������" in text:
            logger.info("Using pypdf being strange PDF")
            return self.get_document_text_pypdf(file_path=file_path)

        if len(text) < MIN_DOC_TEXT_LENGHT_ACCEPTED:
            logger.info(f"TEXT: {text}")
            message = f"Document text with less than {MIN_DOC_TEXT_LENGHT_ACCEPTED} characters"
            raise EmptyDocument(message=message, code=998)

        result_dict = {
            "text": text,
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "completion_model": "not provided",
            "completion_model_provider": "not provided",
            "text_chunks": "not provided",
            "type": self.type,
            "input": file_path,
        }

        return result_dict

    def get_document_text_pypdf(self, file_path: str) -> dict:
        """
        Extract text from a document using PyPDF as fallback extraction backend.

        Alternative to get_document_text that uses PyPDF when PyMuPDF fails.
        Downloads from cloud storage if needed, converts non-PDF files, and
        performs quality validation on extracted text.

        Args:
            file_path (str): Path to document file (local path or cloud URI)

        Returns:
            Dictionary containing:
                - text: Extracted document text
                - completion_tokens: Number of completion tokens (0)
                - prompt_tokens: Number of prompt tokens (0)
                - completion_model: Model name ("not provided")
                - completion_model_provider: Model provider ("not provided")
                - text_chunks: Text chunks ("not provided")
                - type: Document type ("document")
                - input: Original file path

        Raises:
            EmptyDocument: If text is empty or fails quality checks
            ExceededMaxPages: If requested page range is invalid
            ClientError: If cloud storage operations fail
            ConversionError: If document conversion fails
        """
        logger.info("Using PyPDF")

        if self.source == "cloud":
            fd, temp_file_path = tempfile.mkstemp()
            try:
                temp_file_path = self.download_document(file_path, temp_file_path)
                logger.info(f"Successfully loaded document from {file_path}")
            finally:
                os.close(fd)
        elif self.source == "local":
            temp_file_path = file_path
            logger.info(f"Successfully loaded document from local path {file_path}")
        else:
            raise ValueError("Invalid OCR source. Choose 'cloud' or 'local'.")

        # Handle PDF conversion and opening
        if os.path.splitext(file_path)[1].lower() != ".pdf":
            logger.info("Converting file to PDF")
            file_prefix = file_path
            temp_file_path = self.convert_doc_to_pdf(file_prefix=file_prefix, input_file=temp_file_path)
            logger.debug(f"temp_file_path post conversion to pdf: {temp_file_path}")
            file = open(temp_file_path, "rb")
            pdf_reader = PdfReader(file)
        else:
            try:
                file = open(temp_file_path, "rb")
                pdf_reader = PdfReader(file)
                logger.info(f"Successfully opened file with temp_file_path: {temp_file_path}")
            except Exception as e:
                logger.info("Converting file to PDF")
                file_prefix = file_path
                temp_file_path = self.convert_doc_to_pdf(file_prefix=file_prefix, input_file=temp_file_path)
                logger.debug(f"temp_file_path post conversion to pdf: {temp_file_path}")
                file = open(temp_file_path, "rb")
                pdf_reader = PdfReader(file)

        total_pages = len(pdf_reader.pages)

        # Validate and adjust page range
        start_page, end_page = self.validate_page_range(total_pages)

        text = ""
        try_not_markdown = True
        if self.markdown_output and self.page_range is None: # and self.page_range is None:
            # Use markitdown for markdown conversion
            logger.info("Converting file to Markdown with Markitdown")

            def convert_to_markdown(path):
                md = MarkItDown()
                return md.convert(path).markdown

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(convert_to_markdown, temp_file_path)
            try:
                text = future.result(timeout=self.timeout_minutes * 60 if self.timeout_minutes else None)

                if len(text) >= MIN_DOC_TEXT_LENGHT_ACCEPTED:
                    try_not_markdown = False

            except concurrent.futures.TimeoutError:
                logger.info(f"Markdown conversion timed out after {self.timeout_minutes} minutes")
                try_not_markdown = True
                future.cancel()  # cancels only if not started yet
                executor.shutdown(wait=False, cancel_futures=True)
                executor = None

            except Exception as e:
                logger.info(f"Markdown conversion failed: {e}")
                try_not_markdown = True

            finally:
                if executor is not None:
                    executor.shutdown(wait=True)

        if try_not_markdown:
            try:
                # Original plain text extraction logic
                logger.info("Fallback without Markdown conversion")
                text = ""
                last_pages_text = ""
                last_page_index_to_start = 10

                for page_number in range(start_page, end_page):
                    page = pdf_reader.pages[page_number]
                    page_text = page.extract_text()
                    page_text = self.clean_text(page_text)
                    text += page_text

                    if page.page_number >= (total_pages - last_page_index_to_start):
                        last_pages_text += page_text

                    # Early termination checks
                    if len(text) == 0 and page.page_number == 10:
                        message = "First 10 pages of the document are empty"
                        logger.info(message)
                        os.remove(temp_file_path)
                        raise EmptyDocument(message=message, code=998)
                    if len(text) < MIN_DOC_TEXT_LENGHT_ACCEPTED and page.page_number == 20:
                        message = f"First 20 pages of the document have less than {MIN_DOC_TEXT_LENGHT_ACCEPTED} chars"
                        logger.info(message)
                        os.remove(temp_file_path)
                        raise EmptyDocument(message=message, code=998)
                    if (
                            total_pages >= 500
                            and page.page_number == 10
                            and self.has_repeated_rows(text=text, threshold=100)
                    ):
                        message = "First 10 pages of the document have 100 repeated rows"
                        logger.info(message)
                        os.remove(temp_file_path)
                        raise EmptyDocument(message=message, code=998)
                    if (
                            total_pages >= 500
                            and (page.page_number == total_pages - 1)
                            and self.has_repeated_rows(text=last_pages_text, threshold=100)
                    ):
                        message = "Last 10 pages of the document have 100 repeated rows"
                        logger.info(message)
                        os.remove(temp_file_path)
                        raise EmptyDocument(message=message, code=998)
            except EmptyDocument as e:
                raise e
            except Exception as e:
                logger.info(f"Error during text extraction: {e}")
                raise LoaderError(message="text extraction error", status=422, code="TEXT EXTRACTION ERROR")

        if len(text) == 0:
            message = "No text detected"
            logger.info(message)
            raise EmptyDocument(message=message, code=998)

        if len(text) < MIN_DOC_TEXT_LENGHT_ACCEPTED:
            message = f"Document text with less than {MIN_DOC_TEXT_LENGHT_ACCEPTED} characters"
            raise EmptyDocument(message=message, code=998)

        if self.source == "cloud":
            os.remove(temp_file_path)

        result_dict = {
            "text": text,
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "completion_model": "not provided",
            "completion_model_provider": "not provided",
            "text_chunks": "not provided",
            "type": self.type,
            "input": file_path,
        }

        return result_dict

    # Helper methods

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

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean and normalize extracted text.

        Performs standard text cleaning operations:
        - Replaces double quotes with single quotes
        - Removes excessive newlines
        - Removes special tokens

        Args:
            text (str): Raw text to clean

        Returns:
            str: Cleaned and normalized text
        """
        if text:
            text = text.replace('"', "'")
            text = re.sub(r"\n\s*\n", "\n", text)
            text = text.replace('<|endoftext|>', '')
        return text

    @staticmethod
    def has_repeated_rows(text: str, threshold: int = 100) -> bool:
        """
        Check if text contains excessive repeated rows.

        Splits text into lines and counts repetitions to detect potential
        extraction issues or problematic content.

        Args:
            text: Text to analyze for repetitions
            threshold: Maximum allowed repetitions (default: 100)

        Returns:
            True if any line repeats more than threshold times
        """
        # Split the text block into rows/lines
        rows = text.split("\n")
        rows = [row for row in rows if row.strip() != ""]

        # Count occurrences of each row
        row_counts = Counter(rows)

        # Check if any row is repeated at least threshold times
        for count in row_counts.values():
            if count >= threshold:
                return True
        return False

    @staticmethod
    def has_low_text_quality(text: str, chars_threshold: int = 2000) -> bool:
        """
        Check if extracted text has low quality.

        Analyzes a sample of text to determine if it might have OCR or
        extraction issues based on the ratio of valid characters.

        Args:
            text (str): Text to analyze
            chars_threshold (int): Number of characters to sample

        Returns:
            bool: True if text quality is below acceptable threshold
        """
        # Extract a sample of the text
        sample_text = text[:chars_threshold]

        if not sample_text:
            return True

        # Count the number of valid (alphanumeric) characters
        valid_chars = sum(c.isalnum() for c in sample_text)

        # Determine the percentage of valid characters in the sample
        valid_percentage = valid_chars / len(sample_text)

        # Consider the text low quality if 30% or fewer characters are valid
        return valid_percentage <= 0.3

    def load(self, input_path: str) -> dict:
        """
        Load and extract text content from a document file.

        Args:
            input_path (str): Path to document (local path or cloud storage URI)

        Returns:
            Dictionary containing:
                - text: Extracted document text
                - completion_tokens: Number of completion tokens (0)
                - prompt_tokens: Number of prompt tokens (0)
                - completion_model: Model name ("not provided")
                - completion_model_provider: Model provider ("not provided")
                - text_chunks: Text chunks ("not provided")
                - type: Document type ("document")
                - input: Original file path

        Raises:
            EmptyDocument: If text is empty or fails quality checks
            ExceededMaxPages: If requested page range is invalid
            ClientError: If cloud storage operations fail
            ConversionError: If document conversion fails
        """
        return self.get_document_text(file_path=input_path)
