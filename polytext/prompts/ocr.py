OCR_TO_MARKDOWN_PROMPT = """
These are pages from a document. Extract all text content while preserving the structure.
Pay special attention to tables, columns, headers, and any structured content.
Maintain paragraph breaks and formatting.
Your output must be a markdown-formatted text.
In particular, use markdown headings (#, ##, ###, etc.) to reproduce the structure of the document and preserve bold, italic or underlined words and phrases.
Use the first level heading (#) only if you are absolutely sure that the text is the title of the document, otherwise use lower level headings (e.g. ##, ###).
Use LaTeX syntax to represent mathematical formulas, equations, and symbols, ensuring they are properly formatted for markdown rendering.
Furthermore, you must omit page numbers in the final text.
In case no readable text is present, write exactly "no readable text present".
"""

OCR_TO_MARKDOWN_NON_LITERAL_FALLBACK_PROMPT = """
Rephrase and reorganize the text content in a coherent markdown format structure.
Do not transcribe the text verbatim, but preserve the meaning of the original content without omitting anything, even apparently minor details.
Pay special attention to tables, columns, headers, and any structured content.
Your output must be a markdown-formatted text.
In particular, use markdown headings (#, ##, ###, etc.) for the structure of the document and use bold, italic or underlined words and phrases.
Use the first level heading (#) only if you are absolutely sure that the text is the title of the document, otherwise use lower level headings (e.g. ##, ###).
Use LaTeX syntax to represent mathematical formulas, equations, and symbols, ensuring they are properly formatted for markdown rendering.
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

First decide whether there is an embedded visual content element inside the document.
An embedded visual content element is a figure that belongs to the document content itself, such as a chart, graph, map, diagram, schema, scientific illustration, photo, artwork, portrait, visual table, or photo or illustration contained inside a book, handout, slide, article, or notes page.

STRICT EXCLUSION RULES:
- DO NOT describe the input image as an object.
- DO NOT describe the page, book page, notebook page, slide, document, scan, photo, screenshot, tablet screen, phone screen, app interface, browser, PDF viewer, margins, highlights, cracks, UI overlays, watermarks, logos, icons, buttons, cursors, or decorative marks.
- DO NOT add [[DESC: ...]] just because the input is a photograph or screenshot of text.
- If the whole input is only a photographed, scanned, or screenshot page of text, transcribe the text only and add no [[DESC: ...]].
- If you are uncertain whether something is an embedded content figure or just the input container or UI, DO NOT add a description.

WHEN TO ADD DESCRIPTIONS:
- Add [[DESC: ...]] only for embedded non-text visual content that is part of the document's meaning.
- Examples that SHOULD be described: a chart inside a textbook page, a diagram inside notes, a map in a document, a painting, portrait, photograph, or illustration reproduced as a figure in a book or article, and a visual table whose content is not already transcribed.
- Examples that MUST NOT be described: "a page of a book", "a screenshot of an app", "a tablet showing text", "a document page with highlighted text", "Knowunity button", "Studocu logo", "page number", "decorative icon".

FORMAT:
- Insert each description where the embedded figure appears in the reading order.
- If an embedded figure visually interrupts a sentence, place the description after the nearest complete sentence or phrase, then continue with the remaining text.
- Use exactly this format: [[DESC: ...]].
- Keep descriptions brief and functional.
- Each image description MUST be written in the same language as the document and its transcription, even if the embedded figure contains text in a different language.
- For charts, diagrams, maps, schemas, and visual tables, include labels, relationships, axes, trends, hierarchy, and meaningful text only if not already transcribed elsewhere.

Remember: false negatives are better than false positives. If in doubt, omit [[DESC: ...]].
"""


def build_ocr_prompt(base_prompt: str, include_image_descriptions: bool = False) -> str:
    if not include_image_descriptions:
        return base_prompt
    return f"{base_prompt.strip()}\n\n{OCR_IMAGE_DESCRIPTION_INSTRUCTIONS.strip()}\n"
