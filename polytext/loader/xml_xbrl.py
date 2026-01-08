import os
import logging
import tempfile
from ..loader.downloader.downloader import Downloader
from ..exceptions.base import EmptyDocument, LoaderError

logger = logging.getLogger(__name__)

class XmlXbrlLoader:
    """
    Loader for extracting text from XML and XBRL files.
    
    Supports loading from local file system or cloud storage (S3/GCS).
    """

    def __init__(self, source: str = "local", s3_client=None, document_aws_bucket=None,
                 gcs_client=None, document_gcs_bucket=None, temp_dir: str = 'temp',
                 markdown_output: bool = True, **kwargs):
        """
        Initialize the loader.

        Args:
            source (str): Source type ("cloud" or "local").
            s3_client: Boto3 S3 client (optional).
            document_aws_bucket: S3 bucket name (optional).
            gcs_client: GCS client (optional).
            document_gcs_bucket: GCS bucket name (optional).
            temp_dir: Directory for temporary files.
            markdown_output (bool): Whether to format output as markdown.
        """
        self.source = source
        self.s3_client = s3_client
        self.document_aws_bucket = document_aws_bucket
        self.gcs_client = gcs_client
        self.document_gcs_bucket = document_gcs_bucket
        self.temp_dir = os.path.abspath(temp_dir)
        self.markdown_output = markdown_output
        self.type = "xml_xbrl"
        
        os.makedirs(self.temp_dir, exist_ok=True)

    def _download_file(self, file_path: str) -> str:
        """Downloads file from cloud storage to a temp file."""
        fd, temp_file_path = tempfile.mkstemp(dir=self.temp_dir)
        os.close(fd)
        
        downloader = Downloader(
            s3_client=self.s3_client,
            document_aws_bucket=self.document_aws_bucket,
            gcs_client=self.gcs_client,
            document_gcs_bucket=self.document_gcs_bucket
        )

        try:
            if self.s3_client:
                 downloader.download_file_from_s3(file_path, temp_file_path)
            elif self.gcs_client:
                 downloader.download_file_from_gcs(file_path, temp_file_path)
            else:
                 raise LoaderError("Cloud source specified but no client provided.", code="CONFIG_ERROR")
            
            logger.info(f"Downloaded {file_path} to {temp_file_path}")
            return temp_file_path
        except Exception as e:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise LoaderError(f"Failed to download file: {str(e)}", code="DOWNLOAD_ERROR")

    def load(self, input_path: str) -> dict:
        """
        Load and return the content of an XML/XBRL file.

        Args:
            input_path: Path to the file (local path or cloud key).

        Returns:
            dict: Dictionary containing extracted text and metadata.
        """
        temp_file_path = input_path
        should_cleanup = False

        if self.source == "cloud":
            temp_file_path = self._download_file(input_path)
            should_cleanup = True
        
        try:
            if not os.path.exists(temp_file_path):
                 raise LoaderError(f"File not found: {temp_file_path}", code="FILE_NOT_FOUND")

            try:
                with open(temp_file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            except UnicodeDecodeError:
                # Fallback to latin-1 if utf-8 fails
                 with open(temp_file_path, 'r', encoding='latin-1') as f:
                    text = f.read()
            
            if not text.strip():
                 raise EmptyDocument("File is empty", code="EMPTY_FILE")

            return {
                "text": text,
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "completion_model": "not provided",
                "completion_model_provider": "not provided",
                "text_chunks": "not provided",
                "type": self.type,
                "input": input_path,
            }

        except Exception as e:
             if isinstance(e, (EmptyDocument, LoaderError)):
                 raise
             logger.error(f"Error reading file {input_path}: {e}")
             raise LoaderError(f"Error processing file: {str(e)}", code="PROCESSING_ERROR")
        finally:
            if should_cleanup and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
