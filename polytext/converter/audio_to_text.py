# converter/audio_to_text.py
import os
import logging
import tempfile
import time
import mimetypes
import ffmpeg
from retry import retry
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.api_core import exceptions as google_exceptions

from ..prompts.transcription import AUDIO_TO_MARKDOWN_PROMPT, AUDIO_TO_PLAIN_TEXT_PROMPT
from ..processor.audio_chunker import AudioChunker
from ..processor.text_merger import TextMerger

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    'audio/x-aac', 'audio/flac', 'audio/mp3', 'audio/m4a', 'audio/mpeg',
    'audio/mpga', 'audio/mp4', 'audio/opus', 'audio/pcm', 'audio/wav', 'audio/webm'
}

def compress_and_convert_audio(input_path: str, target_bitrate: str = None, bitrate_quality: int = 9) -> str:
    """
    Compress and convert an audio file to MP3 using ffmpeg.

    Args:
        input_path (str): Path to the original audio file
        target_bitrate (str, optional): Target audio bitrate (e.g. '128k'). If provided, overrides bitrate_quality
        bitrate_quality (int, optional): Variable bitrate quality from 0-9 (9 being lowest). Defaults to 9

    Returns:
        str: Path to the temporary compressed/converted MP3 file

    Raises:
        RuntimeError: If FFmpeg compression/conversion fails

    Notes:
        - Creates a temporary MP3 file that should be deleted after use
        - Converts audio to mono and 16kHz sample rate for smaller file size
        - Uses maximum available CPU threads for faster processing
    """
    # Create temporary file for audio output
    fd, temp_audio_path = tempfile.mkstemp(suffix='.mp3')
    os.close(fd)

    if target_bitrate is not None:
        logger.info(f"Compressing audio to target bitrate: {target_bitrate}")
        ffmpeg.input(input_path).output(
            temp_audio_path,
            audio_bitrate=target_bitrate,
            acodec='libmp3lame',
            ac=1,  # Convert to mono
            ar=16000,  # Lower sample rate
            vn=None,
            threads=0,  # Use maximum available threads
            loglevel='error',  # Reduce logging overhead
        ).run(quiet=True, overwrite_output=True)
    else:
        logger.info(f"Compressing audio to bitrate quality: {bitrate_quality}")
        ffmpeg.input(input_path).output(
            temp_audio_path,
            q=bitrate_quality, # Variable bitrate quality (0-9, 9 being lowest)
            acodec='libmp3lame',
            ac=1,  # Convert to mono
            ar=16000,  # Lower sample rate
            vn=None,
            threads=0,  # Use maximum available threads
            loglevel='error',  # Reduce logging overhead
        ).run(quiet=True, overwrite_output=True)

    logger.info(f"Successfully converted and compressed audio: {temp_audio_path}")
    return temp_audio_path

def transcribe_full_audio(audio_file, markdown_output: bool = False,
                          llm_api_key: str = None,
                          save_transcript_chunks: bool = False) -> str:
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
        save_transcript_chunks (bool, optional): Whether to save chunk transcripts in final output. Defaults to False.

    Returns:
        str: The transcribed text from the audio file.
    """
    converter = AudioToTextConverter(markdown_output=markdown_output, llm_api_key=llm_api_key)
    return converter.transcribe_full_audio(audio_file, save_transcript_chunks)

class AudioToTextConverter:
    def __init__(self, transcription_model: str = "gemini-2.0-flash", transcription_model_provider: str = "google",
                 k: int = 5, min_matches: int = 3, markdown_output: bool = True, llm_api_key: str = None,
                 max_llm_tokens: int = 8000, temp_dir: str = "temp") -> None:
        """
        Initialize the AudioToTextConverter class with a specified transcription model and provider.

        Args:
            transcription_model (str): Model name for transcription. Defaults to "gemini-2.0-flash".
            transcription_model_provider (str): Provider of transcription service. Defaults to "google".
            k (int): Number of words to use when searching for overlap between chunks. Defaults to 5.
            min_matches (int): Minimum matching words for chunk merging. Defaults to 3.
            markdown_output (bool): Enable markdown formatting in output. Defaults to True.
            llm_api_key (str, optional): Override API key for language model. Defaults to None.
            max_llm_tokens (int): Maximum number of tokens for the language model output. Defaults to 8000.
            temp_dir (str): Directory for temporary files. Defaults to "temp".

        Raises:
            OSError: If temp directory creation fails
            ValueError: If invalid model or provider specified
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

    @retry(
        (
                google_exceptions.DeadlineExceeded,
                google_exceptions.ResourceExhausted,
                google_exceptions.ServiceUnavailable,
                google_exceptions.InternalServerError
        ),
        tries=8,
        delay=1,
        backoff=2,
        logger=logger,
    )
    def transcribe_audio(self, audio_file: str) -> dict:
        """
        Transcribe audio using a specified model and prompt template.

        Args:
            audio_file (str): Path to the audio file to be transcribed.

        Returns:
            dict: Dictionary containing:
                - transcript (str): The transcribed text
                - completion_tokens (int): Number of tokens in completion
                - prompt_tokens (int): Number of tokens in prompt

        Raises:
            ValueError: If the audio file format is not recognized.
            Exception: For any other errors during the transcription process.
        """

        start_time = time.time()

        if self.markdown_output:
            logger.info("Using prompt for markdown format")
            # Convert the text to markdown format
            prompt_template = AUDIO_TO_MARKDOWN_PROMPT
        else:
            logger.info("Using prompt for plain text format")
            # Convert the text to plain text format
            prompt_template = AUDIO_TO_PLAIN_TEXT_PROMPT

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

        logger.info(f"Completion tokens: {response.usage_metadata.candidates_token_count}")
        logger.info(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")

        response_dict = {"transcript": response.text,
                         "completion_tokens": response.usage_metadata.candidates_token_count,
                         "prompt_tokens": response.usage_metadata.prompt_token_count}

        logger.info(f"Transcribed text from {audio_file} using {self.transcription_model} in {time_elapsed:.2f} seconds")
        return response_dict

    def process_chunk(self, chunk: dict, index: int) -> tuple[int, dict]:
        """Process a single audio chunk and return its transcript"""
        logger.info(f"Transcribing chunk {index + 1}...")
        transcript_dict = self.transcribe_audio(chunk["file_path"])

        return index, transcript_dict

    def transcribe_full_audio(self,
            audio_path: str, save_transcript_chunks: bool = False) -> dict:
        """
        Process and transcribe a long audio file by chunking, parallel transcription, and merging.

        Args:
            audio_path (str): Path to the audio file to be transcribed
            save_transcript_chunks (bool, optional): Whether to save chunk transcripts in final output. Defaults to False.

        Returns:
            dict: Dictionary containing:
                - text (str): The final merged transcript
                - completion_tokens (int): Total number of completion tokens used
                - prompt_tokens (int): Total number of prompt tokens used
                - completion_model (str): Name of the transcription model used
                - completion_model_provider (str): Provider of the transcription model

        Raises:
            ValueError: If the audio file format is not recognized
            RuntimeError: If there's an error during audio processing or transcription
        """
        processed_audio_path = None
        try:
            logger.info(f"Processing audio file {audio_path}...")
            file_size = os.path.getsize(audio_path)
            logger.info(f"Audio file size: {file_size / (1024 * 1024):.2f} MB")

            mime_type, _ = mimetypes.guess_type(audio_path)
            logger.info(f"Original MIME type: {mime_type}")

            # Check if conversion and/or compression is needed
            needs_conversion = mime_type not in SUPPORTED_MIME_TYPES
            needs_compression = file_size > 20 * 1024 * 1024

            # If you need at least one of the two, apply compress_and_convert_audio
            if needs_conversion:  # or needs_compression:
                logger.info("Audio file needs conversion, processing file...")
                processed_audio_path = compress_and_convert_audio(audio_path)
                used_file = processed_audio_path
                logger.info(f"Audio file processed (conversion): {used_file}")
            else:
                used_file = audio_path
                logger.info("Audio file is already in supported format")

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
                    executor.submit(self.process_chunk, chunk, i): i
                    for i, chunk in enumerate(chunks)
                }

                # Process completed transcriptions in order of completion
                completion_tokens = 0
                prompt_tokens = 0
                for future in as_completed(future_to_chunk):
                    index, transcript_dict = future.result()
                    chunks[index]["transcript"] = transcript_dict["transcript"]
                    transcript_chunks[index] = transcript_dict["transcript"]
                    completion_tokens += transcript_dict["completion_tokens"]
                    prompt_tokens += transcript_dict["prompt_tokens"]

            text_merger = TextMerger()
            # Merge all transcripts
            full_text_merged_dict = text_merger.merge_chunks_with_llm_sequential(chunks=transcript_chunks)

            final_transcript_dict = {
                "text": full_text_merged_dict["full_text_merged"],
                "completion_tokens": completion_tokens + full_text_merged_dict["completion_tokens"],
                "prompt_tokens": prompt_tokens + full_text_merged_dict["prompt_tokens"],
                "completion_model": self.transcription_model,
                "completion_model_provider": self.transcription_model_provider
            }
            if save_transcript_chunks:
                final_transcript_dict["text_chunks"] = transcript_chunks

            # Clean up temporary files
            if len(chunks) > 1:
                chunker.cleanup_temp_files(chunks)

            return final_transcript_dict
        finally:
            # Clean up the temporary compressed file
            if processed_audio_path and os.path.exists(processed_audio_path):
                os.remove(processed_audio_path)

