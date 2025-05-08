# converter/audio_to_text.py
from fontTools.ttLib.tables.otConverters import BaseConverter

from ..prompts.transcription import AUDIO_TO_MARKDOWN_PROMPT, AUDIO_TO_PLAIN_TEXT_PROMPT

def transcribe_audio(audio_file, markdown_output=True):
    """
        Convenience function to transcribe an audio file into text, optionally formatted as Markdown.

        This function initializes an `AudioToTextConverter` instance and uses it
        to transcribe the provided audio file. The output can be formatted as
        Markdown or plain text based on the `markdown_output` parameter.

        Args:
            audio_file (str): Path to the audio file to be transcribed.
            markdown_output (bool, optional): If True, the transcription will be
                formatted as Markdown. Defaults to True.

        Returns:
            str: The transcribed text from the audio file.
        """
    converter = AudioToTextConverter()
    return converter.transcribe_audio(audio_file, markdown_output=True)

class AudioToTextConverter:
    def __init__(self, transcription_model="gemini-2.0-flash", transcription_model_provider="google"):
        """
        Initialize VideoLoader with optional S3 or GCS configuration.

        Args:
            s3_client: Boto3 S3 client instance for AWS operations (optional)
            document_aws_bucket (str): Default S3 bucket name for document storage (optional)
        """
        self.transcription_model = transcription_model
        self.transcription_model_provider = transcription_model_provider

    def transcribe_audio(self, audio_file, markdown_output=True):
        """
        Transcribe audio using a specified model and prompt template.

        Args:
            audio_file (str): Path to the audio file

        Returns:
            str: Transcribed text
        """
        if markdown_output:
            # Convert the text to markdown format
            prompt_template = AUDIO_TO_MARKDOWN_PROMPT
        else:
            # Convert the text to plain text format
            prompt_template = AUDIO_TO_PLAIN_TEXT_PROMPT

        # Placeholder for actual transcription logic
        # This should call the appropriate API or library for transcription
        # For example, using OpenAI's Whisper or any other service

        # Simulate transcription process
        transcribed_text = f"Transcribed text from {audio_file} using {self.transcription_model}"
        return transcribed_text
