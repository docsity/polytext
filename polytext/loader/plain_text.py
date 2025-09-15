# Standard library imports
import os
import tempfile
import logging
import mimetypes

# Local imports
from ..converter.text_to_md import text_to_md
from ..converter.html_to_md import html_to_md
from ..exceptions import EmptyDocument

logger = logging.getLogger(__name__)


class PlainTextLoader:
    """
    Loader for processing and formatting plain text documents.

    This class handles the extraction, optional formatting (e.g., Markdown), and metadata aggregation
    for plain text inputs. It supports saving processed chunks and uses a language model if configured.
    """

    def __init__(
        self,
        llm_api_key: str = None,
        markdown_output: bool = True,
        temp_dir: str = "temp",
        **kwargs,
    ) -> None:
        """
        Initialize the PlainTextLoader with configuration for LLM, output formatting, and temp storage.

        Args:
            llm_api_key (str, optional): API key for the language model used for processing.
            markdown_output (bool, optional): If True, format the extracted text as Markdown. Defaults to True.
            temp_dir (str, optional): Directory for temporary/intermediate files. Defaults to 'temp'.
            save_transcript_chunks (bool, optional): Whether to include processed chunks in the output.
        """
        self.llm_api_key = llm_api_key
        self.save_transcript_chunks = kwargs.get("save_transcript_chunks", False)
        self.temp_dir = temp_dir
        self.markdown_output = markdown_output
        self.type = "text"

        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

    def get_plain_text(self, plain_text: str) -> dict:
        """
        Process and optionally format plain text, returning extracted content and metadata.

        Args:
            plain_text (str): The input plain text to process.

        Returns:
            dict: Dictionary with the following keys:
                - text (str): Final processed text.
                - completion_tokens (int): Number of tokens used in generation.
                - prompt_tokens (int): Number of prompt tokens used.
                - completion_model (str): Name of the model used.
                - completion_model_provider (str): Provider of the model.
                - text_chunks (list, optional): List of processed chunks if `save_transcript_chunks` is True.
                - type (str): Type of the processed source ("plain_text").
                - input (str): Identifier for the input ("plain_text").

        Raises:
            Exception: If an error occurs during processing or formatting.
        """

        result_dict = text_to_md(
            transcript_text=plain_text,
            markdown_output=self.markdown_output,
            llm_api_key=self.llm_api_key,
            save_transcript_chunks=self.save_transcript_chunks,
        )

        result_dict["type"] = self.type
        result_dict["input"] = "plain_text"

        if len(result_dict["text"].strip()) == 0:
            raise EmptyDocument(f"No text extracted. The text may be empty or not contain any transcribable content.")

        return result_dict

    def load(self, input_path: str) -> dict:
        """
        Loads and processes text from the specified input file.

        The method detects the MIME type of the input file:
          - If the file is HTML (`text/html`), it reads the file and converts its content to Markdown using `html_to_md`.
          - If the file is plain text, it processes the content directly using `get_plain_text`.

        Args:
            input_path (str): The path to the input file (plain text or HTML).

        Returns:
            dict: A dictionary containing the processed text and metadata:
                - text (str): The extracted and optionally formatted text.
                - completion_tokens (int, optional): Number of completion tokens (if available).
                - prompt_tokens (int, optional): Number of prompt tokens (if available).
                - completion_model (str, optional): Name of the model used (if available).
                - completion_model_provider (str, optional): Provider of the model (if available).
                - text_chunks (list, optional): List of processed text chunks (if enabled).
                - type (str): Type of the processed source ("plain_text").
                - input (str): The input file path.
        """
        mime_type, _ = mimetypes.guess_type(input_path)
        if mime_type == "text/html":
            result_dict = html_to_md(input_path)
            result_dict["type"] = "text"
            result_dict["input"] = input_path
            return result_dict
        else:
            return self.get_plain_text(plain_text=input_path)
