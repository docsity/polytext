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

TEXT_PROMPT = """Format the following text better.
Language: Keep the language of the document.
Important: Do not include any additional explanations or comments outside of the transcription.
"""