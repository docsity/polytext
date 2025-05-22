# Standard library imports
import os
import tempfile
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

    @retry(requests.exceptions.RequestException, tries=3, delay=2)
    def get_text_from_url(self, url: str, markdown_output: bool = True) -> dict:
        """
        Retrieves the HTML content, converts it to Markdown, and optionally to plain text.
        Handles request failures with retry and a final try-except block.

        Args:
            url (str): The URL of the HTML page to fetch.
            markdown_output (bool, optional): Whether to output the Markdown content.

        Returns:
            str: The converted Markdown or plain text content, or None in case of irreversible error.
        """
        result = html_to_md(url)
        if markdown_output:
            result["text"] = md_to_text(result["text"])

        return result