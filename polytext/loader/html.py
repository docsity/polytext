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
        url (str): The URL of the HTML page to fetch.
        is_text (bool): If True, the output will be plain text instead of Markdown.
        temp_dir (str): The directory where temporary files are stored.
        output_path (str): Full path to the output markdown file.
    """

    def __init__(self, url: str, is_text=False, temp_dir='temp'):
        """
        Initialize the HtmlLoader object.

        Args:
            url (str): The URL to fetch the HTML from.
            is_text (bool, optional): Whether to convert Markdown to plain text. Defaults to False.
            temp_dir (str, optional): Directory for temporary files. Defaults to 'temp'.
        """

        self.url = url
        self.is_text = is_text

        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

        self.output_path = os.path.join(self.temp_dir, f"page.md")


    @retry(requests.exceptions.RequestException, tries=3, delay=2)
    def get_html(self):
        """
        Retrieves the HTML content, converts it to Markdown, and optionally to plain text.
        Handles request failures with retry and a final try-except block.

        Returns:
            str: The converted Markdown or plain text content, or None in case of irreversible error.
        """
        try:
            result = html_to_md(self.url)
            if self.is_text:
                result = md_to_text(result)

            final_text_dict = {
                "text": result,
            }
            return final_text_dict
        except requests.exceptions.RequestException as e:
            print(f"Irreversible error during fetching of {self.url} after retries: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred in get_html: {e}")
            return None