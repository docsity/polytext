# notebook.py
# Standard library imports
import os
import json
import logging
import tempfile
from pathlib import Path

# Local imports
from ..loader.downloader.downloader import Downloader
from ..exceptions import EmptyDocument

logger = logging.getLogger(__name__)


class NotebookLoader:
    """
    Loader for Jupyter notebook (.ipynb) files.
    """

    def __init__(self, source, markdown_output=True, s3_client=None, document_aws_bucket=None, gcs_client=None,
                 document_gcs_bucket=None, temp_dir="temp", **kwargs):
        """
        Initialize the NotebookLoader with cloud storage configurations.

        Args:
            source (str): Source of the notebook file. Must be either "cloud" or "local".
            markdown_output (bool, optional): If True, preserves markdown formatting. Defaults to True.
            s3_client (boto3.client, optional): AWS S3 client for S3 operations. Defaults to None.
            document_aws_bucket (str, optional): S3 bucket name for document storage. Defaults to None.
            gcs_client (google.cloud.storage.Client, optional): GCS client for Cloud Storage operations.
                Defaults to None.
            document_gcs_bucket (str, optional): GCS bucket name for document storage. Defaults to None.
            temp_dir (str, optional): Path for temporary file storage. Defaults to "temp".
            **kwargs: Additional options.
                - include_outputs (bool): Whether to include cell outputs. Defaults to True.
                - max_output_length (int, optional): Max length for output text. Defaults to None.
                - traceback (bool): Whether to include error tracebacks. Defaults to False.
        """
        self.source = source
        self.markdown_output = markdown_output
        self.s3_client = s3_client
        self.document_aws_bucket = document_aws_bucket
        self.gcs_client = gcs_client
        self.document_gcs_bucket = document_gcs_bucket
        self.include_outputs = kwargs.get("include_outputs", True)
        self.max_output_length = kwargs.get("max_output_length", None)
        self.traceback = kwargs.get("traceback", False)
        self.type = "notebook"

        # Set up custom temp directory
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

    def download_notebook(self, file_path, temp_file_path):
        """
        Download a notebook file from S3 or GCS to a local temporary path.
        """
        if self.s3_client is not None:
            downloader = Downloader(s3_client=self.s3_client, document_aws_bucket=self.document_aws_bucket)
            downloader.download_file_from_s3(file_path, temp_file_path)
            logger.info(f'Downloaded {file_path} to {temp_file_path}')
            return temp_file_path
        elif self.gcs_client is not None:
            downloader = Downloader(gcs_client=self.gcs_client, document_gcs_bucket=self.document_gcs_bucket)
            downloader.download_file_from_gcs(file_path, temp_file_path)
            logger.info(f'Downloaded {file_path} to {temp_file_path}')
            return temp_file_path
        else:
            raise ValueError("No cloud storage client provided. Please provide either an S3 or GCS client.")

    def concatenate_cells(self, cell: dict) -> str:
        """Combine cells information in a readable format."""
        cell_type = cell.get("cell_type", "unknown")
        source = cell.get("source", "")
        
        # Source can be a list of strings or a single string
        if isinstance(source, list):
            source = "".join(source)

        content = f"'{cell_type}' cell: \n{source}\n"

        if self.include_outputs and cell_type == "code":
            outputs = cell.get("outputs", [])
            for output in outputs:
                if "ename" in output:
                    error_name = output.get("ename", "")
                    error_value = output.get("evalue", "")
                    content += f"gives error '{error_name}', with description '{error_value}'\n"
                    if self.traceback:
                        tb = output.get("traceback", [])
                        if isinstance(tb, list):
                            tb = "\n".join(tb)
                        content += f"and traceback '{tb}'\n"
                elif output.get("output_type") == "stream":
                    text = output.get("text", "")
                    if isinstance(text, list):
                        text = "".join(text)
                    if self.max_output_length:
                        min_output = min(self.max_output_length, len(text))
                        text = text[:min_output]
                    content += f"with output: '{text}'\n"
                elif output.get("output_type") in ["execute_result", "display_data"]:
                    data = output.get("data", {})
                    if "text/plain" in data:
                        text = data["text/plain"]
                        if isinstance(text, list):
                            text = "".join(text)
                        if self.max_output_length:
                            min_output = min(self.max_output_length, len(text))
                            text = text[:min_output]
                        content += f"with output: '{text}'\n"

        return content + "\n"

    def get_text_from_file(self, file_path: str) -> str:
        """Read and parse the .ipynb file."""
        logger.info(f"Reading notebook from file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                d = json.load(f)

            cells = d.get("cells", [])
            text_cells = [self.concatenate_cells(cell) for cell in cells]
            return "".join(text_cells)

        except FileNotFoundError:
            logger.info(f"File not found: {file_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON in {file_path}: {e}")
            raise ValueError(f"Invalid notebook format: {e}")
        except Exception as e:
            logger.info(f"Error reading file {file_path}: {e}")
            raise

    def get_text_from_notebook(self, file_path):
        """Extract text from a notebook file from either cloud storage or local path."""
        logger.info("Starting text extraction from notebook...")

        if self.source == "cloud":
            fd, temp_file_path = tempfile.mkstemp(suffix=".ipynb")
            try:
                self.download_notebook(file_path, temp_file_path)
                logger.info(f"Successfully loaded notebook from {file_path}")
                text_from_notebook = self.get_text_from_file(temp_file_path)
            finally:
                os.close(fd)
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    logger.info(f"Removed temporary file {temp_file_path}")
        elif self.source == "local":
            text_from_notebook = self.get_text_from_file(file_path)
            logger.info(f"Successfully loaded notebook from local path {file_path}")
        else:
            raise ValueError("Invalid notebook source. Choose 'cloud' or 'local'.")

        if not text_from_notebook.strip():
            raise EmptyDocument(f"No text extracted from notebook: {file_path}")

        result_dict = {
            "text": text_from_notebook,
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "completion_model": "not provided",
            "completion_model_provider": "not provided",
            "text_chunk": "not provided",
            "type": self.type,
            "input": file_path,
        }

        return result_dict

    def load(self, input_path: str) -> dict:
        """Load and extract text content from notebook file."""
        return self.get_text_from_notebook(file_path=input_path)
