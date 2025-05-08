AUDIO_TO_MARKDOWN_PROMPT = """I need you to transcribe and format the content of this audio file into Markdown.
I would like you to follow these steps:
1. Audio Transcription: Accurately transcribe the content of the audio file into text.
2. Text Structuring: Structure the text in a logical and readable manner, including:
    - Identification and separation of speakers (if there are multiple speakers).
    - Grouping of related phrases and concepts into paragraphs.
    - Application of a hierarchy of titles and subtitles (using #, ##, etc.) based on the flow of the speech and the importance of the topics.
    - Highlighting of key words or important phrases using ** or _.
3. Markdown Formatting: Apply the appropriate Markdown syntax for the formatting identified in the previous step (titles, paragraphs, emphasis, lists, etc.).
4. Markdown Output: Provide the result as a block of text formatted in Markdown.
Important: Do not include any additional explanations or comments outside of the Markdown formatting."""

AUDIO_TO_PLAIN_TEXT_PROMPT = """Transcribe the following audio to plain text format.
Important: Do not include any additional explanations or comments outside of the transcription."""
