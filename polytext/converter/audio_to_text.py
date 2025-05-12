# converter/audio_to_text.py
import os
import logging
import tempfile
import time
import mimetypes
import ffmpeg
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..prompts.transcription import AUDIO_TO_MARKDOWN_PROMPT, AUDIO_TO_PLAIN_TEXT_PROMPT, \
    AUDIO_TO_MARKDOWN_MINIMAL_PROMPT
from ..processor.audio_chunker import AudioChunker
from ..processor.text_merger import merge_chunks

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    'audio/x-aac', 'audio/flac', 'audio/mp3', 'audio/m4a', 'audio/mpeg',
    'audio/mpga', 'audio/mp4', 'audio/opus', 'audio/pcm', 'audio/wav', 'audio/webm'
}

def compress_and_convert_audio(input_path: str, target_bitrate="128k"):
    """
    Compress and convert an audio file to AAC using ffmpeg.

    Args:
        input_path (str): Original audio file path.
        output_path (str): Path to save the converted/compressed audio file.
        target_bitrate (str): Desired audio bitrate, e.g., "128k", etc.
    """
    try:
        # Create temporary file for audio output
        fd, temp_audio_path = tempfile.mkstemp(suffix='.aac')
        os.close(fd)

        ffmpeg.input(input_path).output(
            temp_audio_path,
            audio_bitrate=target_bitrate,
            acodec='aac'
        ).run(quiet=True, overwrite_output=True)

        logger.info(f"Successfully converted and compressed audio: {temp_audio_path}")
        return temp_audio_path
    except Exception as e:
        raise RuntimeError(f"FFmpeg error during audio compression/conversion: {e}") from e

def transcribe_full_audio(audio_file, markdown_output=False, llm_api_key=None):
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
    converter = AudioToTextConverter(markdown_output=markdown_output, llm_api_key=llm_api_key)
    return converter.transcribe_full_audio(audio_file)

class AudioToTextConverter:
    def __init__(self, transcription_model="gemini-2.0-flash", transcription_model_provider="google",
                 k=5, min_matches=3, markdown_output=True, llm_api_key=None, max_llm_tokens=8000, temp_dir="temp"):
        """
        Initialize the AudioToTextConverter class with a specified transcription model and provider.

        Args:
            transcription_model (str, optional): The name of the transcription model to use.
                Defaults to "gemini-2.0-flash".
            transcription_model_provider (str, optional): The provider of the transcription model.
                Defaults to "google".
            k (int, optional): Number of words to use when searching for overlap between chunks.
                Defaults to 5.
            min_matches (int, optional): Minimum number of matching words required to merge chunks.
                Defaults to 3.
            markdown_output (bool, optional): Whether to format the output as Markdown.
                Defaults to True.
            llm_api_key (str, optional): API key for the language model service.
                Defaults to None.
            max_llm_tokens (int, optional): Maximum number of tokens for the language model output.
                Defaults to 8000.
        """
        self.transcription_model = transcription_model
        self.transcription_model_provider = transcription_model_provider
        self.k = k
        self.min_matches = min_matches
        self.markdown_output = markdown_output
        self.llm_api_key = llm_api_key
        self.max_llm_tokens = max_llm_tokens
        self.chunked_audio = False

        # Set up custom temp directory
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        tempfile.tempdir = self.temp_dir

    def transcribe_audio(self, audio_file):
        """
        Transcribe audio using a specified model and prompt template.

        Args:
            audio_file (str): Path to the audio file to be transcribed.

        Returns:
            str: The transcribed text from the audio file.

        Raises:
            ValueError: If the audio file format is not recognized.
            Exception: For any other errors during the transcription process.
        """

        start_time = time.time()

        if self.markdown_output and not self.chunked_audio:
            # Convert the text to markdown format
            prompt_template = AUDIO_TO_MARKDOWN_PROMPT
        elif self.markdown_output and self.chunked_audio:
            # Convert the text to minimal markdown format
            prompt_template = AUDIO_TO_MARKDOWN_MINIMAL_PROMPT
        else:
            # Convert the text to plain text format
            prompt_template = AUDIO_TO_PLAIN_TEXT_PROMPT

        try:
            if self.llm_api_key:
                logger.info("Using provided Google API key")
                client = genai.Client(api_key=self.llm_api_key)
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
                logger.info("Audio file size does not exceed 20MB")
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

    def process_chunk(self, chunk, index, save_intermediate):
        """Process a single audio chunk and return its transcript"""
        logger.info(f"Transcribing chunk {index + 1}...")
        transcript = self.transcribe_audio(chunk["file_path"])

        if save_intermediate:
            with open(f"transcript_chunk_{index}.txt", "w") as f:
                f.write(transcript)

        return index, transcript

    def transcribe_full_audio(self,
            audio_path,
            save_intermediate=True):
        """Process a long audio file by chunking, transcribing, and merging"""
        processed_audio_path = None
        try:
            file_size = os.path.getsize(audio_path)
            logger.info(f"Audio file size: {file_size / (1024 * 1024):.2f} MB")

            mime_type, _ = mimetypes.guess_type(audio_path)
            logger.info(f"Original MIME type: {mime_type}")

            # Check if conversion and/or compression is needed
            needs_conversion = mime_type not in SUPPORTED_MIME_TYPES
            needs_compression = file_size > 20 * 1024 * 1024

            # If you need at least one of the two, apply compress_and_convert_audio
            if needs_conversion:  # or needs_compression:
                logger.info("Audio file needs conversion/compression, processing file...")
                processed_audio_path = compress_and_convert_audio(audio_path)
                used_file = processed_audio_path
                logger.info(f"Audio file processed (conversion/compression): {used_file}")
            else:
                used_file = audio_path
                logger.info("Audio file is already in supported format and under size limit.")

            # Create chunker and extract chunks
            logger.info("Creating AudioChunker instance...")
            chunker = AudioChunker(used_file, max_llm_tokens=self.max_llm_tokens)
            chunks = chunker.extract_chunks()

            logger.info(f"chunks: {chunks}")

            logger.info(f"Split audio into {len(chunks)} chunks")
            if len(chunks) > 1 and self.markdown_output:
                logger.info("Audio chunking is needed, returning minimal markdown output")
                # self.markdown_output=False
                self.chunked_audio = True

            # Transcribe each chunk
            transcript_chunks = [""] * len(chunks)  # Pre-allocate list to maintain order
            with ThreadPoolExecutor() as executor:
                # Submit all chunks to the thread pool
                future_to_chunk = {
                    executor.submit(self.process_chunk, chunk, i, save_intermediate): i
                    for i, chunk in enumerate(chunks)
                }

                # Process completed transcriptions in order of completion
                for future in as_completed(future_to_chunk):
                    index, transcript = future.result()
                    chunks[index]["transcript"] = transcript
                    transcript_chunks[index] = transcript

            # Merge all transcripts
            final_transcript = merge_chunks(chunks=transcript_chunks, k=self.k, min_matches=self.min_matches)

            # Clean up temporary files
            chunker.cleanup_temp_files(chunks)

            return final_transcript
        finally:
            # Clean up the temporary compressed file
            if processed_audio_path and os.path.exists(processed_audio_path):
                os.remove(processed_audio_path)

