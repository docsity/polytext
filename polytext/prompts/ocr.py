OCR_TO_MARKDOWN_PROMPT = """
These are pages from a document. Extract all text content while preserving the structure.
Pay special attention to tables, columns, headers, and any structured content.
Maintain paragraph breaks and formatting.
Your output must be a markdown-formatted text.
In particular, use markdown headings (#, ##, ###, etc.) to reproduce the structure of the document and preserve bold, italic or underlined words and phrases.
Use the first level heading (#) only if you are absolutely sure that the text is the title of the document, otherwise use lower level headings (e.g. ##, ###).
Furthermore, you must omit page numbers in the final text.
In case no readable text is present, write exactly "no readable text present".
"""

OCR_TO_PLAIN_TEXT_PROMPT = """
These are pages from a document. Extract all text content while preserving the structure.
Maintain paragraph breaks and formatting.
Your output must be a plain text.
"""

OCR_IMAGE_DESCRIPTION_INSTRUCTIONS = """
Image description instructions:
- When meaningful non-text visual content is present, insert a concise description using exactly this format: [Image description: ...].
- Insert the description where the image appears in the reading order.
- If an image visually interrupts a sentence, place the description after the nearest complete sentence or phrase, then continue with the remaining text.
- Keep descriptions brief and functional.
- For diagrams, schemas, charts, maps, screenshots, and visual tables, include all meaningful information needed to understand the context, including labels, relationships, axes, trends, hierarchy, and text inside the image when it is not already transcribed elsewhere.
- Do not describe purely decorative marks, borders, logos, or icons unless they carry document meaning.
"""


def build_ocr_prompt(base_prompt: str, include_image_descriptions: bool = False) -> str:
    if not include_image_descriptions:
        return base_prompt
    return f"{base_prompt.strip()}\n\n{OCR_IMAGE_DESCRIPTION_INSTRUCTIONS.strip()}\n"
