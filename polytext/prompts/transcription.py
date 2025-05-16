AUDIO_TO_MARKDOWN_PROMPT_OLD = """I need you to transcribe and format the content of this audio file into Markdown.
I would like you to follow these steps:
1. Audio Transcription: Accurately transcribe the content of the audio file into text.
2. Text Structuring:
    - You must group related phrases and concepts into paragraphs.
    - You must apply a hierarchy of subheadings (using only ##, ###) based on the flow of the speech and the importance of the topics.
    - You must highlight key words or important phrases using ** or _.
    - You must ensure proper punctuation, spacing, and consistency throughout.
    - You must remove filler words (such as uh, um\'s, ah\'s, etc.).
    - You must not write ```markdown at the beginning or end of the text.
Important:
- You must use both Markdown subheadings (##, ###) and paragraphs to make the transcript easy to read and understand and highlight key words or important phrases.
- Do not include any additional explanations or comments outside of the Markdown formatting."""

AUDIO_TO_PLAIN_TEXT_PROMPT = """Transcribe the following audio to plain text format.
Important: Do not include any additional explanations or comments outside of the transcription."""

# AUDIO_TO_MARKDOWN_PROMPT = """Your goal is to transcribe and format the content of this audio file into Markdown in order to have a precise but clearly readable transcription of the audio.
# Accurately transcribe the content of the audio file and adhere to the following guidelines for markdown formatting:
#     - You must group related phrases and concepts into paragraphs.
#     - You must apply a hierarchy of subheadings (using only ##, ###) based on the flow of the speech and the importance of the topics.
#     - You must highlight key words or important phrases using ** or _.
#     - You must ensure proper punctuation, spacing, and consistency throughout.
#     - You must remove filler words (such as uh, um\'s, ah\'s, etc.).
#     - You must not write ```markdown at the beginning or end of the text.
#     - You must not include any additional explanations or comments outside of the Markdown formatting.
# For the markdown formatting of the transcript give priority to the use of subheadings (##, ###) and paragraphs."""