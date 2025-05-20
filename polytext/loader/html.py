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

    Attributes:
        is_text (bool): If True, the output will be plain text instead of Markdown.
    """

    def __init__(self, is_text=False):
        """
        Initialize the HtmlLoader object.

        Args:
            is_text (bool, optional): Whether to convert Markdown to plain text. Defaults to False.
        """
        self.is_text = is_text


    @retry(requests.exceptions.RequestException, tries=3, delay=2)
    def get_text_from_url(self, url: str):
        """
        Retrieves the HTML content, converts it to Markdown, and optionally to plain text.
        Handles request failures with retry and a final try-except block.

        Args:
            url (str): The URL of the HTML page to fetch.

        Returns:
            str: The converted Markdown or plain text content, or None in case of irreversible error.
        """
        try:
            result = html_to_md(url)
            if self.is_text:
                result = md_to_text(result)

            final_text_dict = {
                "text": result,
            }
            return final_text_dict
        except requests.exceptions.RequestException as e:
            print(f"Irreversible error during fetching of {url} after retries: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred in get_html: {e}")
            return None