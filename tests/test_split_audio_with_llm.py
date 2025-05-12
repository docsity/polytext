import time
import logging
import mimetypes
import os
import sys
from google import genai
from google.genai import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

logger = logging.getLogger(__name__)

SPLIT_AUDIO_PROMPT = """Given this audio file provide:
1. Total duration of the entire audio file in minutes and seconds
2. Suggested split points at natural speech pauses or sentence boundaries to obtain three equal-length chunks that preserve complete sentences
Provide the exact timestamps for the split points in the format HH:MM:SS, and ensure that the split points do not cut off any words or phrases.
Be sure to consider the entire audio file.

Answer only with a valid JSON object containing the following keys:
{{"total_length": "HH:MM:SS", "split_points": ["HH:MM:SS", "HH:MM:SS"]}}
"""

# SPLIT_AUDIO_PROMPT = "Are you able to give me the exact length of this audio file?"

SPLIT_AUDIO_PROMPT = """I want you to transcribe this audio file into text providing timestamps."""

def split_audio(audio_file, llm_api_key=None):
    """

    """

    start_time = time.time()

    prompt_template = SPLIT_AUDIO_PROMPT

    transcription_model = "gemini-2.5-flash-preview-04-17"  # "gemini-2.5-flash-preview-04-17"

    try:
        if llm_api_key:
            print("Using provided Google API key")
            client = genai.Client(api_key=llm_api_key)
        else:
            print("Using Google API key from ENV")
            client = genai.Client()

        config = types.GenerateContentConfig(
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ]
        )

        file_size = os.path.getsize(audio_file)
        print(f"Audio file size: {file_size / (1024 * 1024):.2f} MB")
        if file_size > 30 * 1024 * 1024:
            print("Audio file size exceeds 20MB, uploading file before transcription")

            myfile = client.files.upload(file=audio_file)

            response = client.models.count_tokens(
                model='gemini-2.0-flash',
                contents=[myfile]
            )
            print(f"File size in tokens: {response}")

            print(f"Uploaded file: {myfile.name} - Starting transcription...")

            response = client.models.generate_content(
                model=transcription_model,
                contents=[prompt_template, myfile],
                config=config
            )

            client.files.delete(name=myfile.name)

        else:
            with open(audio_file, "rb") as f:
                audio_data = f.read()

            # Determine mimetype
            mime_type, _ = mimetypes.guess_type(audio_file)
            if mime_type is None:
                raise ValueError("Audio format not recognized")

            content = []
            if prompt_template:
                content.append(prompt_template)
            content.append({"mime_type": mime_type, "data": audio_data})

            response = client.models.generate_content(
                model=transcription_model,
                contents=[
                    prompt_template,
                    types.Part.from_bytes(
                        data=audio_data,
                        mime_type=mime_type,
                    )
                ],
                config=config
            )

        end_time = time.time()
        time_elapsed = end_time - start_time

        print(
            f"Transcribed text from {audio_file} using {transcription_model} in {time_elapsed:.2f} seconds")
        return response.text

    except Exception as e:
        logger.error(f"Error during audio transcription: {str(e)}")
        raise


file_path = "/Users/marcodelgiudice/Projects/polytext/tmp46evneuz_audio.mp3"
response = split_audio(file_path)

print(response)

import ipdb; ipdb.set_trace()

