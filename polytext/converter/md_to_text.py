# converter/md_to_text.py
import re


def md_to_text(md: str) -> str:
    """
    Convert a Markdown string to plain text by removing formatting syntax
    such as headers, emphasis, lists, links, images, code blocks, etc.

    Args:
        md (str): A string containing Markdown-formatted text.

    Returns:
        str: A plain text representation of the original Markdown content.
    """

    # Remove code blocks ```...```
    md = re.sub(r'```.*?```', '', md, flags=re.DOTALL)

    # Remove inline code `...`
    md = re.sub(r'`([^`]*)`', r'\1', md)

    # Remove images ![alt](url)
    md = re.sub(r'!\[.*?]\(.*?\)', '', md)

    # Convert links [text](url) → text
    md = re.sub(r'\[([^]]+)]\([^)]+\)', r'\1', md)

    # Remove headers (e.g., #, ##)
    md = re.sub(r'^\s{0,3}#{1,6}\s+', '', md, flags=re.MULTILINE)

    # Remove bold/italic markers **, __
    md = re.sub(r'(\*\*|__)(.*?)\1', r'\2', md)

    # Remove italic/single emphasis markers * or _
    md = re.sub(r'([*_])(.*?)\1', r'\2', md)

    # Remove blockquotes >
    md = re.sub(r'^\s{0,3}>\s?', '', md, flags=re.MULTILINE)

    # Remove unordered and ordered list markers
    md = re.sub(r'^\s*[-*+]\s+', '', md, flags=re.MULTILINE)
    md = re.sub(r'^\s*\d+\.\s+', '', md, flags=re.MULTILINE)

    # Normalize whitespace
    md = re.sub(r'\n{2,}', '\n', md)
    md = re.sub(r'[ \t]+', ' ', md)

    return md.strip()