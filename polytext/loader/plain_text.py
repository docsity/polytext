# Standard library imports
import os
import tempfile
import logging

# Local imports
from ..converter.text_to_md import text_to_md
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
        self.type = "plain_text"

        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

        self.output_path = os.path.join(self.temp_dir, f"plain_text.txt")

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
            output_path=self.output_path,
            save_transcript_chunks=self.save_transcript_chunks,
        )

        result_dict["type"] = self.type
        result_dict["input"] = "plain_text"

        return result_dict

    def load(self, input_path: str) -> dict:
        """
        Load and process plain text from the given input.

        Args:
            input_path (str): The plain text input to process.

        Returns:
            dict: Dictionary containing the processed text and associated metadata.
        """
        return self.get_plain_text(plain_text=input_path)
