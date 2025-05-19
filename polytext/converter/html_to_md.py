from markitdown import MarkItDown


def html_to_md(html):
    """
       Convert an HTML string to Markdown using MarkItDown.

       Args:
           html (str): A string containing the HTML content to be converted.

       Returns:
           str: A Markdown-formatted string generated from the input HTML.
    """

    md = MarkItDown()
    md_text = md.convert(html).markdown
    return md_text
