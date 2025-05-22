from markitdown import MarkItDown


def html_to_md(html: str) -> dict:
    """
       Convert an HTML string to Markdown using MarkItDown.

       Args:
           html (str): A string containing the HTML content to be converted.

       Returns:
           str: A Markdown-formatted string generated from the input HTML.
    """
    md = MarkItDown()
    md_text = md.convert(html).markdown

    result = {
            "text": md_text,
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "completion_model": 'not provided',
            "completion_model_provider": 'not provided'
    }
    return result
