OCR_TO_MARKDOWN_PROMPT = """
These are pages from a PDF document. Extract all text content while preserving the structure.
Pay special attention to tables, columns, headers, and any structured content.
Maintain paragraph breaks and formatting.
Your output must be a markdown-formatted text.
In particular, use markdown headings (#, ##, ###, etc.) to reproduce the structure of the document and preserve bold, italic or underlined words and phrases.
Use the first level heading (#) only if you are absolutely sure that the text is the title of the document, otherwise use lower level headings (e.g. ##, ###).
Furthermore, you must omit page numbers in the final text.
"""

OCR_TO_PLAIN_TEXT_PROMPT = """
"""