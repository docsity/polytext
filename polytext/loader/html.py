# Standard library imports
import logging
import requests

# Local imports
from ..converter import md_to_text, html_to_md

# External imports
from retry import retry

logger = logging.getLogger(__name__)


class HtmlLoader:
    """
    A utility class for loading HTML content from a URL, converting it to Markdown,
    and optionally extracting plain text from the Markdown.
    """

    def __init__(self, markdown_output: bool = True) -> None:
        """
        Initialize the HtmlLoader object.

        Args:
            markdown_output (bool): Whether to convert the text to Markdown format. Defaults to True.
        """
        self.markdown_output = markdown_output
        self.type = "link"

    @retry(requests.exceptions.RequestException, tries=3, delay=2)
    def get_text_from_url(self, url: str) -> dict:
        """
        Retrieves the HTML content, converts it to Markdown, and optionally to plain text.
        Handles request failures with retry and a final try-except block.

        Args:
            url (str): The URL of the HTML page to fetch.

        Returns:
            str: The converted Markdown or plain text content, or None in case of irreversible error.
        """
        result_dict = html_to_md(url)
        result_dict["type"] = self.type

        if not self.markdown_output:
            result_dict["text"] = md_to_text(result_dict["text"])

        return result_dict

    def load(self, input_path: str) -> dict:
        """
        Extract text content from a web page URL.

        Args:
            input_path (str): A list of one URLs.

        Returns:
            dict: A dictionary containing the extracted text and any associated metadata.
        """
        return self.get_text_from_url(url=input_path)