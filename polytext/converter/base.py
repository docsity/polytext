import re


class BaseConverter:
    def __init__(self):
        pass
    """
    Base class for all converters
    """

    @staticmethod
    def format_subtitles(text: str) -> str:
        """
        Format a text by adjusting spacing around Markdown-style subtitles (## or ###).

        Args:
            text: Text to be formatted.

        Returns:
            Formatted text with consistent spacing around subtitles and no excessive blank lines.
        """
        # Ensure there is a blank line before and after ## or ### subtitles
        # Prevent breaking the line between the subtitle and its content
        pattern = r'(?<!\n)\n?(#{2,3} .+?)\n?(?!\n)'

        def replacer(match):
            subtitle = match.group(1).strip()
            return f"\n\n{subtitle}\n\n"

        formatted_text = re.sub(pattern, replacer, text)

        # Remove any excessive blank lines
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)

        return formatted_text