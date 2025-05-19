# converter/md_to_text.py
import logging
import re

logger = logging.getLogger(__name__)


def md_to_text(md: str) -> str:
    """
        Convert a Markdown string to plain text by removing formatting syntax
        such as headers, emphasis, lists, links, images, code blocks, etc.

        Args:
            md (str): A string containing Markdown-formatted text.

        Returns:
            str: A plain text representation of the original Markdown content.
    """

    # Rimuove codice in blocco ```...```
    md = re.sub(r'```.*?```', '', md, flags=re.DOTALL)

    # Rimuove codice inline `...`
    md = re.sub(r'`([^`]*)`', r'\1', md)

    # Rimuove immagini ![alt](url)
    md = re.sub(r'!\[.*?\]\(.*?\)', '', md)

    # Sostituisce i link [text](url) → text
    md = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', md)

    # Rimuove intestazioni (#, ##, ecc.)
    md = re.sub(r'^\s{0,3}#{1,6}\s+', '', md, flags=re.MULTILINE)

    # Rimuove asterischi e underscore per grassetto/italico
    md = re.sub(r'(\*\*|__)(.*?)\1', r'\2', md)
    md = re.sub(r'(\*|_)(.*?)\1', r'\2', md)

    # Rimuove blockquote >
    md = re.sub(r'^\s{0,3}>\s?', '', md, flags=re.MULTILINE)

    # Rimuove liste puntate o numerate
    md = re.sub(r'^\s*[-*+]\s+', '', md, flags=re.MULTILINE)
    md = re.sub(r'^\s*\d+\.\s+', '', md, flags=re.MULTILINE)

    # Normalizza spazi bianchi
    md = re.sub(r'\n{2,}', '\n', md)
    md = re.sub(r'[ \t]+', ' ', md)

    return md.strip()

