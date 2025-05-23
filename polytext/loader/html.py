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

    def __init__(self) -> None:
        """
        Initialize the HtmlLoader object.
        """
        self.type = "html"

    @retry(requests.exceptions.RequestException, tries=3, delay=2)
    def get_text_from_url(self, url: str, markdown_output: bool = True, **kwargs) -> dict:
        """
        Retrieves the HTML content, converts it to Markdown, and optionally to plain text.
        Handles request failures with retry and a final try-except block.

        Args:
            url (str): The URL of the HTML page to fetch.
            markdown_output (bool, optional): Whether to output the Markdown content.

        Returns:
            str: The converted Markdown or plain text content, or None in case of irreversible error.
        """
        result_dict = html_to_md(url)
        result_dict["type"] = self.type

        if not markdown_output:
            result_dict["text"] = md_to_text(result_dict["text"])

        return result_dict

    def load(self, input_list: list[str], markdown_output: bool = True, **kwargs) -> dict:
        """
        Extract text content from a web page URL.

        Args:
            input_list (list[str]): A list of one URLs.
            markdown_output (bool, default: True): Whether to format the extracted text as Markdown.
            **kwargs: Additional options passed to the extraction logic.

        Returns:
            dict: A dictionary containing the extracted text and any associated metadata.
        """
        return self.get_text_from_url(url=input_list[0], markdown_output=markdown_output, **kwargs)