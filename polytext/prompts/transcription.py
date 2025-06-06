AUDIO_TO_MARKDOWN_PROMPT = """I need you to transcribe and format the content of this audio file into Markdown.
You must follow these instructions exactly:
1. **Audio Transcription** (only if human speech is detected):
    - Accurately transcribe the spoken content of the audio file into text.
2. **Text Structuring**:
    - You must group related phrases and concepts into paragraphs.
    - You must apply a hierarchy of subheadings (using only ##, ###) based on the flow of the speech and the importance of the topics.
    - You must highlight key words or important phrases using ** or _.
    - You must ensure proper punctuation, spacing, and consistency throughout.
    - You must remove filler words (such as uh, um\'s, ah\'s, etc.).
    - You must not write ```markdown at the beginning or end of the text.
**Important rules**:
- You must use both Markdown subheadings (##, ###) and paragraphs to make the transcript easy to read and understand and highlight key words or important phrases.
- Do not include any additional explanations or comments outside of the Markdown formatting.
- If **no human speech is detected**, return `no human speech detected` as a string.
"""

AUDIO_TO_PLAIN_TEXT_PROMPT = """Transcribe the following audio to plain text format.
You must follow these instructions exactly:
1. **Audio Transcription** (only if human speech is detected):
    - Accurately transcribe the spoken content of the audio file into text.
**Important rules**:
- Do not include any additional explanations or comments outside of the transcription."
- If **no human speech is detected**, return `no human speech detected` as a string
"""

VIDEO_TO_MARKDOWN_PROMPT = """I need you to transcribe only the human speech of the youtube video into Markdown.
You must follow these instructions exactly:
1. **Video Transcription only if human speech is detected**:
    - Accurately transcribe the spoken human content of the video file into text.
2. **Text Structuring**:
    - You must group related phrases and concepts into paragraphs.
    - You must apply a hierarchy of subheadings (using only ##, ###) based on the flow of the speech and the importance of the topics.
    - You must highlight key words or important phrases using ** or _.
    - You must ensure proper punctuation, spacing, and consistency throughout.
    - You must remove filler words (such as uh, um\'s, ah\'s, etc.).
    - You must not write ```markdown at the beginning or end of the text.
**Important rules**:
- You must use both Markdown subheadings (##, ###) and paragraphs to make the transcript easy to read and understand and highlight key words or important phrases.
- Do not include any additional explanations or comments outside of the Markdown formatting.
- If **no human voice detected** or you cannot get the video transcript, return `no human voice detected` as a string.
"""

VIDEO_TO_TEXT_PROMPT = """Transcribe the following human speech of this youtube video into plain text.
You must follow these instructions exactly:
1. **Audio Transcription** (only if human speech is detected):
    - Accurately transcribe the spoken content of the audio file into text.
**Important rules**:
- Do not include any additional explanations or comments outside of the transcription."
- If **no human voice detected** or you cannot get the video transcript, return `no human voice detected` as a string.
"""

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