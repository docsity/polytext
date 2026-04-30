TEXT_TO_MARKDOWN_PROMPT = """
I need you to convert and format the text into Markdown.

Please follow these steps:
1. Text Structuring: Structure the text in a logical and readable manner, including:
    - Grouping related ideas or topics into clear paragraphs.
    - Use of a hierarchy of subtitles (##, ###) to reflect topic flow and importance.
    - Highlighting key words or important phrases using ** or _.
    - Ensure proper punctuation, spacing, and overall consistency.
    - Remove filler words (such as uh, um, ah, etc.).
    - Do not wrap the output in code blocks like ```markdown.
2. Markdown Formatting: Apply appropriate Markdown syntax for headings, emphasis, lists, etc.
3. Markdown Output: Provide the result as a clean Markdown-formatted text block.
4. Language: keep the language of the document.
Important: Do not include any additional explanations or comments outside of the Markdown formatting.
"""

TEXT_TO_MARKDOWN_FORMULA_PROMPT = """
I need you to convert and format the text into Markdown.

Please follow these steps:
1. Text Structuring:
    - Group related ideas or topics into clear paragraphs.
    - Use a hierarchy of subtitles (##, ###) to reflect topic flow and importance.
    - Ensure proper punctuation, spacing, and overall consistency.
    - Do not wrap the output in code blocks like ```markdown.
2. Formula Handling:
    - Identify every mathematical formula, equation, scientific formula, or formula-like notation.
    - For inline formulas, use strictly the delimiter `$...$`.
    - For standalone block formulas, use strictly the delimiter `$$...$$`.
    - Preserve formulas in the same logical position in which they appear in the input.
    - Treat formulas inside delimiters as immutable content.
    - Do not translate, paraphrase, simplify, or rewrite the meaning of formulas.
    - Use standard LaTeX syntax for subscripts and superscripts where applicable, for example `x_{i}` and `a^{2}`.
    - If a formula is already expressed in a recognizable symbolic form, preserve it rather than rewriting it.
3. Content Preservation:
    - Do not summarize the text.
    - Do not remove technical notation that may be part of a formula.
    - Do not rewrite chemistry or mathematics into descriptive prose.
4. Markdown Output:
    - Apply appropriate Markdown syntax for headings, emphasis, and lists when useful.
5. Language:
    - Keep the language of the document.

Important:
    - Output only the final Markdown.
    - Do not include explanations or comments outside of the Markdown.
"""

TEXT_PROMPT = """Format the following text better.
Language: Keep the language of the document.
Important: Do not include any additional explanations or comments outside of the transcription.
"""
