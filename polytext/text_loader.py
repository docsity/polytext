# text_loader.py
# Standard library imports
import os
import re
import tempfile
import logging
from collections import Counter

# Third-party imports
from pypdf import PdfReader
import fitz  # PyMuPDF
from botocore.exceptions import ClientError

# Local imports
from .converter import DocumentConverter
from .exceptions import EmptyDocument, ExceededMaxPages

logger = logging.getLogger(__name__)


class TextLoader:
    """Loads and extracts text from documents, with optional S3 support."""

    def __init__(self, s3_client=None, document_aws_bucket=None):
        """
        Initialize TextLoader.

        Args:
            s3_client: S3 client for downloading files (optional)
            document_aws_bucket: Default S3 bucket name (optional)
        """
        self.converter = DocumentConverter()
        self.s3_client = s3_client
        self.document_aws_bucket = document_aws_bucket

    # S3-related methods

    def download_file_from_s3(self, bucket, file_path, temp_file_path):
        """
        Download a file from S3 to a local temporary path.

        Args:
            bucket (str): S3 bucket name
            file_path (str): Path to file in S3
            temp_file_path (str): Local path to save the file

        Returns:
            str: Path to the downloaded file (may be converted to PDF)
        """
        try:
            self.s3_client.download_file(Bucket=bucket, Key=file_path, Filename=temp_file_path)
            logger.info(f'Downloaded {file_path} to {temp_file_path}')
        except ClientError as e:
            logger.info(e)
            try:
                self.s3_client.download_file(Bucket=bucket,
                                             Key=file_path.replace(".pdf", ".PDF"),
                                             Filename=temp_file_path)
            except Exception as e:
                file_prefix = file_path
                temp_file_path = self.convert_doc_to_pdf(bucket=bucket,
                                                         file_prefix=file_prefix,
                                                         input_file=temp_file_path)
        return temp_file_path

    def convert_doc_to_pdf(self, bucket, file_prefix, input_file):
        """
        Convert a document from S3 to PDF.

        Args:
            bucket (str): S3 bucket name
            file_prefix (str): Prefix to match files in S3
            input_file (str): Local path to save the downloaded file

        Returns:
            str: Path to the converted PDF file
        """
        logger.info(f"bucket: {bucket}")
        logger.info(f"file_prefix: {file_prefix}")
        logger.info(f"input_file: {input_file}")

        # Create a temporary file for output
        fd, output_file = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)  # Close file descriptor explicitly

        # List objects in S3 bucket
        response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=file_prefix)

        if 'Contents' not in response or not response['Contents']:
            raise FileNotFoundError("No matching file found in S3 bucket.")

        # Get the first matching object
        matching_file = response['Contents'][0]['Key']

        # Download the file
        self.s3_client.download_file(
            Bucket=bucket,
            Key=matching_file,
            Filename=input_file
        )
        logger.info("Using LibreOffice")
        self.converter.convert_to_pdf(input_file=input_file, output_file=output_file)
        logger.info("Document converted to pdf")
        os.remove(input_file)
        return output_file

    # PDF text extraction methods

    def get_document_text(self, doc_data, page_range=None):
        """
        Extract text from a document in S3 using PyMuPDF.

        Args:
            doc_data (dict): Dictionary containing file_path and optional bucket
            page_range (tuple, optional): Tuple of (start_page, end_page)

        Returns:
            str: Extracted text from the document
        """
        logger.debug("Using PyMuPDF")
        file_path = doc_data["file_path"]

        fd, temp_file_path = tempfile.mkstemp()
        if doc_data.get("bucket"):
            bucket = doc_data.get("bucket")
        else:
            bucket = self.document_aws_bucket

        if os.path.splitext(file_path)[1].lower() != ".pdf":
            logger.info("Converting file to PDF")
            file_prefix = file_path
            temp_file_path = self.convert_doc_to_pdf(bucket=bucket, file_prefix=file_prefix, input_file=temp_file_path)
            pdf_document = fitz.open(temp_file_path)
        else:
            temp_file_path = self.download_file_from_s3(bucket, file_path, temp_file_path)
            try:
                pdf_document = fitz.open(temp_file_path)
                logger.info(f"Successfully opened file with temp_file_path: {temp_file_path}")
            except Exception as e:
                logger.info("Converting file to PDF")
                file_prefix = file_path
                temp_file_path = self.convert_doc_to_pdf(bucket=bucket, file_prefix=file_prefix, input_file=temp_file_path)
                pdf_document = fitz.open(temp_file_path)

        text = ""
        last_pages_text = ""
        last_page_index_to_start = 10
        total_pages = pdf_document.page_count
        logger.info(f"Total pages: {total_pages}")

        # Validate and adjust page range
        start_page, end_page = self.validate_page_range(page_range, total_pages)

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

            if len(text) < 800 and page_number == 20:
                message = "First 20 pages of the document have less than 800 chars"
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

        pdf_document.close()
        os.remove(temp_file_path)

        if len(text) == 0:
            message = "No text detected"
            logger.info(message)
            raise EmptyDocument(message=message, code=998)
        if "������������������������������������������" in text:
            logger.info("Using pypdf being strange PDF")
            return self.get_document_text_pypdf(bucket=bucket, file_path=file_path, page_range=page_range)
        if len(text) < 800:
            message = "Document text with less than 800 characters"
            raise EmptyDocument(message=message, code=998)

        return text

    def get_document_text_pypdf(self, bucket, file_path, page_range=None):
        """
        Extract text from a document in S3 using PyPDF.

        Args:
            bucket (str): S3 bucket name
            file_path (str): Path to file in S3
            page_range (tuple, optional): Tuple of (start_page, end_page)

        Returns:
            str: Extracted text from the document
        """
        logger.info("Using PyPDF")

        fd, temp_file_path = tempfile.mkstemp()

        if os.path.splitext(file_path)[1].lower() != ".pdf":
            logger.info("Converting file to PDF")
            file_prefix = file_path
            temp_file_path = self.convert_doc_to_pdf(bucket=bucket, file_prefix=file_prefix, input_file=temp_file_path)
            logger.debug(f"temp_file_path post conversion to pdf: {temp_file_path}")
            file = open(temp_file_path, "rb")
            pdf_reader = PdfReader(file)
        else:
            temp_file_path = self.download_file_from_s3(bucket, file_path, temp_file_path)
            logger.debug(f"temp_file_path: {temp_file_path}")
            try:
                file = open(temp_file_path, "rb")
                pdf_reader = PdfReader(file)
                logger.info(f"Successfully opened file with temp_file_path: {temp_file_path}")
            except Exception as e:
                logger.info("Converting file to PDF")
                file_prefix = file_path
                temp_file_path = self.convert_doc_to_pdf(bucket=bucket, file_prefix=file_prefix,
                                                         input_file=temp_file_path)
                logger.debug(f"temp_file_path post conversion to pdf: {temp_file_path}")
                file = open(temp_file_path, "rb")
                pdf_reader = PdfReader(file)

        text = ""
        last_pages_text = ""
        last_page_index_to_start = 10
        total_pages = len(pdf_reader.pages)

        # Validate and adjust page range
        start_page, end_page = self.validate_page_range(page_range, total_pages)

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
            if len(text) < 800 and page.page_number == 20:
                message = "First 20 pages of the document have less than 800 chars"
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

        if len(text) == 0:
            message = "No text detected"
            logger.info(message)
            raise EmptyDocument(message=message, code=998)

        os.remove(temp_file_path)
        return text

    def extract_text_from_file(self, file_path, page_range=None, backend='auto'):
        """
        Extract text from a local file.

        Args:
            file_path (str): Path to the local file
            page_range (tuple, optional): Optional tuple of (start_page, end_page).
                                         Pages are 1-indexed (first page is 1).
            backend (str, optional): Text extraction backend: 'auto', 'pymupdf', or 'pypdf'

        Returns:
            str: Extracted text from the document
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{file_path}' does not exist.")

        # Validate backend option
        valid_backends = ['auto', 'pymupdf', 'pypdf']
        if backend not in valid_backends:
            raise ValueError(f"Invalid backend '{backend}'. Must be one of {valid_backends}")

        # Determine backend to use if 'auto'
        if backend == 'auto':
            backend = 'pymupdf'  # Default to PyMuPDF for better extraction quality

        # Check if file needs conversion to PDF
        file_ext = os.path.splitext(file_path)[1].lower()
        temp_pdf_path = None

        try:
            if file_ext != '.pdf':
                logger.info(f"Converting {file_ext} file to PDF...")
                fd, temp_pdf_path = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)  # Close the file descriptor

                # Convert to PDF using the converter
                pdf_path = self.converter.convert_to_pdf(file_path, temp_pdf_path)
            else:
                pdf_path = file_path

            text = ""

            # Extract text using PyMuPDF
            if backend == 'pymupdf':
                logger.debug("Using PyMuPDF for text extraction")
                try:
                    pdf_document = fitz.open(pdf_path)
                    try:
                        total_pages = pdf_document.page_count

                        # Validate and adjust page range
                        start_page, end_page = self.validate_page_range(page_range, total_pages)

                        for page_number in range(start_page, end_page):
                            page = pdf_document.load_page(page_number)
                            page_text = page.get_text("text", flags=16)  # Use cleaner text extraction
                            page_text = self.clean_text(page_text)
                            text += page_text

                    finally:
                        pdf_document.close()

                    # Check for strange characters that might indicate PyMuPDF issues
                    if "������������������������������������������" in text:
                        logger.warning("PyMuPDF extracted unusual characters. Switching to PyPDF.")
                        backend = 'pypdf'
                    elif len(text.strip()) == 0:
                        logger.warning("PyMuPDF extracted no text. Switching to PyPDF.")
                        backend = 'pypdf'
                    else:
                        # If text was successfully extracted, return it
                        return text

                except Exception as e:
                    logger.warning(f"PyMuPDF extraction failed: {str(e)}. Trying PyPDF.")
                    backend = 'pypdf'  # Try PyPDF as a fallback

            # Extract text using PyPDF
            if backend == 'pypdf':
                logger.debug("Using PyPDF for text extraction")
                with open(pdf_path, "rb") as file:
                    pdf_reader = PdfReader(file)
                    total_pages = len(pdf_reader.pages)

                    # Validate and adjust page range
                    start_page, end_page = self.validate_page_range(page_range, total_pages)

                    # Reset text if we're falling back from PyMuPDF
                    text = ""

                    for page_number in range(start_page, end_page):
                        page = pdf_reader.pages[page_number]
                        page_text = page.extract_text()
                        page_text = self.clean_text(page_text)
                        text += page_text

            if not text.strip():
                message = "No text detected in the document"
                logger.info(message)
                raise EmptyDocument(message=message, code=998)

            return text

        finally:
            # Clean up temporary file
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {temp_pdf_path}: {str(e)}")

    # Helper methods

    @staticmethod
    def validate_page_range(page_range, total_pages):
        """
        Validate and normalize the page range.

        Args:
            page_range: Tuple of (start_page, end_page) or None (1-indexed)
            total_pages: Total number of pages in the document

        Returns:
            tuple: (start_page, end_page) normalized to 0-indexed
        """
        if page_range:
            logger.info(f"Using page range: {page_range[0]} - {page_range[1]}")
            if page_range[1] > total_pages or page_range[0] < 1:
                raise ExceededMaxPages(
                    message=f"Requested page range {page_range} exceeds document length ({total_pages})",
                    code=998
                )
            start_page = max(0, page_range[0] - 1)  # Convert to 0-indexed
            end_page = min(page_range[1], total_pages)
        else:
            start_page = 0
            end_page = total_pages

        return start_page, end_page

    @staticmethod
    def clean_text(text):
        """
        Clean and normalize extracted text.

        Args:
            text: The raw text to clean

        Returns:
            str: The cleaned text
        """
        if text:
            text = text.replace('"', "'")
            text = re.sub(r"\n\s*\n", "\n", text)
            text = text.replace('<|endoftext|>', '')
        return text

    @staticmethod
    def has_repeated_rows(text, threshold=100):
        """
        Check if text contains repeated lines above a certain threshold.

        Args:
            text (str): The text to analyze
            threshold (int): Minimum number of repetitions to trigger detection

        Returns:
            bool: True if repeated lines are detected
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
    def has_low_text_quality(text, chars_threshold=2000):
        """
        Check if the text has low quality (potential OCR issues).

        Args:
            text (str): The text to analyze
            chars_threshold (int): Number of characters to sample

        Returns:
            bool: True if the text quality is low
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
