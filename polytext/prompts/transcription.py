AUDIO_TO_MARKDOWN_PROMPT = """I need you to transcribe and format the content of this audio file into Markdown.

You must follow these instructions EXACTLY:

1. **Verbatim Audio Transcription** (MANDATORY):
   - Transcribe the spoken content **word-for-word** exactly as it is spoken.
   - **Do NOT summarize, reinterpret, paraphrase, or improve the text in any way.**
   - **Do NOT convert speech into notes or structured explanations.**
   - Preserve the original phrasing, sentence structure, and wording.
   - Maintain the original language of the speaker.

2. **Minimal Cleaning (Allowed Transformations ONLY):**
   - You may remove ONLY non-meaningful filler sounds such as: "uh", "um", "ah".
   - You may fix obvious punctuation for readability (e.g., commas, periods), but **without changing meaning or structure**.
   - Do NOT merge, split, or rewrite sentences beyond punctuation.

3. **Markdown Formatting (WITHOUT altering content):**
   - Organize the transcript into paragraphs based on natural pauses in speech.
   - Add Markdown subheadings (##, ###) ONLY to reflect clear topic shifts in the speech.
   - Headings must be **neutral labels**, not summaries or reinterpretations.
   - You may highlight a few exact words or phrases using **bold** or _italic_, but **only if they appear exactly as spoken**.

4. **Strict Prohibitions:**
   - Do NOT summarize.
   - Do NOT rephrase.
   - Do NOT add explanations, clarifications, or inferred meaning.
   - Do NOT transform the content into notes, bullet points, or structured knowledge.
   - Do NOT introduce any information not explicitly spoken in the audio.

5. **Output Rules:**
   - Output ONLY the Markdown transcript.
   - Do NOT include ```markdown or any code block markers.
   - Do NOT include any commentary or meta text.

6. **No Speech Case:**
   - If no human speech is detected, return exactly:
     no human speech detected
"""

AUDIO_TO_PLAIN_TEXT_PROMPT = """Transcribe the following audio to plain text format.
You must follow these instructions exactly:
1. **Audio Transcription** (only if human speech is detected):
    - Accurately transcribe the spoken content of the audio file into text, maintaining the original language.
**Important rules**:
- Do not include any additional explanations or comments outside of the transcription."
- If **no human speech is detected**, return `no human speech detected` as a string
"""

VIDEO_TO_MARKDOWN_PROMPT_OLD = """I need you to transcribe only the spoken human dialogue from the YouTube video and present it in Markdown format.
You must follow these instructions exactly:
1. **Video Transcription only if human speech is detected**:
    - Accurately transcribe the spoken human content of the video file into text, maintaining the original language.
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

VIDEO_TO_TEXT_PROMPT_OLD = """Transcribe the following human speech of this youtube video into plain text.
You must follow these instructions exactly:
1. **Audio Transcription** (only if human speech is detected):
    - Accurately transcribe the spoken content of the audio file into text, maintaining the original language.
**Important rules**:
- Do not include any additional explanations or comments outside of the transcription."
- If **no human voice detected** or you cannot get the video transcript, return `no human voice detected` as a string.
"""

VIDEO_TO_TEXT_PROMPT = """
I need you to transcribe and format the content of this audio file into plain text. You must follow these instructions EXACTLY: 
1. **Verbatim Audio Transcription** (MANDATORY):
- Transcribe the spoken content **word-for-word** exactly as it is spoken.
- **Do NOT summarize, reinterpret, paraphrase, or improve the text in any way.** 
- **Do NOT convert speech into notes or structured explanations.**
- Preserve the original phrasing, sentence structure, and wording.
- Maintain the original language of the speaker.

2. **Minimal Cleaning (Allowed Transformations ONLY):**
- You may remove ONLY non-meaningful filler sounds such as: "uh", "um", "ah".
- You may fix obvious punctuation for readability (e.g., commas, periods), but **without changing meaning or structure**.
- Do NOT merge, split, or rewrite sentences beyond punctuation. 

3. **Formatting (WITHOUT altering content):**
- Organize the transcript into paragraphs based on natural pauses in speech.
- Headings must be **neutral labels**, not summaries or reinterpretations.
- You may highlight a few exact words or phrases using **bold** or _italic_, but **only if they appear exactly as spoken**.

4. **Strict Prohibitions:**
- Do NOT summarize.
- Do NOT rephrase.
- Do NOT add explanations, clarifications, or inferred meaning.
- Do NOT transform the content into notes, bullet points, or structured knowledge.
- Do NOT introduce any information not explicitly spoken in the audio.

5. **Output Rules:**
- Output ONLY the plain text transcript.
- Do NOT include any commentary or meta text.

6. **No Speech Case:**
   - If no human speech is detected, return exactly:
     no human speech detected
"""

VIDEO_TO_MARKDOWN_PROMPT = """"
I need you to transcribe and format the content of this audio file into Markdown. You must follow these instructions EXACTLY: 
1. **Verbatim Audio Transcription** (MANDATORY):
- Transcribe the spoken content **word-for-word** exactly as it is spoken.
- **Do NOT summarize, reinterpret, paraphrase, or improve the text in any way.** 
- **Do NOT convert speech into notes or structured explanations.**
- Preserve the original phrasing, sentence structure, and wording.
- Maintain the original language of the speaker.

2. **Minimal Cleaning (Allowed Transformations ONLY):**
- You may remove ONLY non-meaningful filler sounds such as: "uh", "um", "ah".
- You may fix obvious punctuation for readability (e.g., commas, periods), but **without changing meaning or structure**.
- Do NOT merge, split, or rewrite sentences beyond punctuation. 

3. **Markdown Formatting (WITHOUT altering content):**
- Organize the transcript into paragraphs based on natural pauses in speech.
- Add Markdown subheadings (##, ###) ONLY to reflect clear topic shifts in the speech.
- Headings must be **neutral labels**, not summaries or reinterpretations.
- You may highlight a few exact words or phrases using **bold** or _italic_, but **only if they appear exactly as spoken**.

4. **Strict Prohibitions:**
- Do NOT summarize.
- Do NOT rephrase.
- Do NOT add explanations, clarifications, or inferred meaning.
- Do NOT transform the content into notes, bullet points, or structured knowledge.
- Do NOT introduce any information not explicitly spoken in the audio.

5. **Output Rules:**
- Output ONLY the Markdown transcript.
- Do NOT include markdown or any code block markers.
- Do NOT include any commentary or meta text.

6. **No Speech Case:**
   - If no human speech is detected, return exactly:
     no human speech detected
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