# converter/audio_to_text.py
import os
import logging
import time
import mimetypes
import google.generativeai as generativeai
from google import genai
from google.genai import types
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from ..prompts.transcription import AUDIO_TO_MARKDOWN_PROMPT, AUDIO_TO_PLAIN_TEXT_PROMPT

logger = logging.getLogger(__name__)

def transcribe_audio(audio_file, markdown_output=True, llm_api_key=None):
    """
    Convenience function to transcribe an audio file into text, optionally formatted as Markdown.

    This function initializes an `AudioToTextConverter` instance and uses it
    to transcribe the provided audio file. The output can be formatted as
    Markdown or plain text based on the `markdown_output` parameter.

    Args:
        audio_file (str): Path to the audio file to be transcribed.
        markdown_output (bool, optional): If True, the transcription will be
            formatted as Markdown. Defaults to True.
        llm_api_key (str, optional): API key for the LLM service. If provided, it will override the default configuration.

    Returns:
        str: The transcribed text from the audio file.
    """
    converter = AudioToTextConverter()
    return converter.transcribe_audio(audio_file, markdown_output, llm_api_key)

class AudioToTextConverter:
    def __init__(self, transcription_model="gemini-2.0-flash", transcription_model_provider="google"):
        """
        Initialize the AudioToTextConverter class with a specified transcription model and provider.

        Args:
            transcription_model (str, optional): The name of the transcription model to use.
                Defaults to "gemini-2.0-flash".
            transcription_model_provider (str, optional): The provider of the transcription model.
                Defaults to "google".z
        """
        self.transcription_model = transcription_model
        self.transcription_model_provider = transcription_model_provider

    def transcribe_audio(self, audio_file, markdown_output=True, llm_api_key=None):
        """
        Transcribe audio using a specified model and prompt template.

        Args:
            audio_file (str): Path to the audio file to be transcribed.
            markdown_output (bool, optional): If True, the transcription will be formatted as Markdown. Defaults to True.
            llm_api_key (str, optional): API key for the LLM service. If provided, it will override the default configuration.

        Returns:
            str: The transcribed text from the audio file.

        Raises:
            ValueError: If the audio file format is not recognized.
            Exception: For any other errors during the transcription process.
        """

        start_time = time.time()

        if markdown_output:
            # Convert the text to markdown format
            prompt_template = AUDIO_TO_MARKDOWN_PROMPT
        else:
            # Convert the text to plain text format
            prompt_template = AUDIO_TO_PLAIN_TEXT_PROMPT

        try:
            # with open(audio_file, "rb") as f:
            #     audio_data = f.read()
            #
            # # Determine mimetype
            # mime_type, _ = mimetypes.guess_type(audio_file)
            # if mime_type is None:
            #     raise ValueError("Audio format not recognized")
            #
            # content = []
            # if prompt_template:
            #     content.append(prompt_template)
            # content.append({"mime_type": mime_type, "data": audio_data})
            #
            # model = generativeai.GenerativeModel(model_name=self.transcription_model)
            #
            # if llm_api_key:
            #     logger.info(f"Using custom Google LLM API key: {llm_api_key}")
            #     generativeai.configure(api_key=llm_api_key)
            #
            #
            # safety_settings = {
            #     HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            #     HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            #     HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            #     HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            # }
            # # generation_config = generativeai.GenerationConfig(temperature=temperature, top_p=top_p,
            # #                                            max_output_tokens=max_tokens,
            # #                                            presence_penalty=presence_penalty,
            # #                                            frequency_penalty=frequency_penalty)
            #
            # response = model.generate_content(contents=content,
            #                                   #generation_config=generation_config,
            #                                   safety_settings=safety_settings
            #                                   )

            if llm_api_key:
                logger.info("Using provided Google API key")
                client = genai.Client(api_key=llm_api_key)
            else:
                logger.info("Using Google API key from ENV")
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
            logger.info(f"Audio file size: {file_size / (1024 * 1024):.2f} MB")
            if file_size > 20 * 1024 * 1024:
                logger.info("Audio file size exceeds 20MB, uploading file before transcription")

                myfile = client.files.upload(file=audio_file)

                response = client.models.count_tokens(
                    model='gemini-2.0-flash',
                    contents=[myfile]
                )
                logger.info(f"File size in tokens: {response}")

                logger.info(f"Uploaded file: {myfile.name} - Starting transcription...")

                response = client.models.generate_content(
                    model=self.transcription_model,
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
                    model=self.transcription_model,
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

            logger.info(f"Transcribed text from {audio_file} using {self.transcription_model} in {time_elapsed:.2f} seconds")
            return response.text

        except Exception as e:
            logger.error(f"Error during audio transcription: {str(e)}")
            raise

