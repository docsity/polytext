# audio.py
import google.generativeai as genai
import logging
import mimetypes

logger = logging.getLogger(__name__)

class AudioLoader:

    def __init__(self, model='gemini-2.0-flash', language='it'):
        self.language = language
        self.model = model

    def transcribe_audio(self, audio_file, prompt_template=None):
        """
        Transcribes audio using Gemini.

        Args:
            audio_file (str): Path to the audio file
            prompt_template (str): Text to guide the transcription (e.g. markdown or text format)

        Returns:
            str: Transcribed text
        """

        try:
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

            model = genai.GenerativeModel(self.model)

            response = model.generate_content(content=content)

            return response.text

        except Exception as e:
            logger.error(f"Error during audio transcription: {str(e)}")
            raise
