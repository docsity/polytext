# converter/ocr_to_text.py
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

from ..prompts.ocr import OCR_TO_MARKDOWN_PROMPT, OCR_TO_PLAIN_TEXT_PROMPT
from ..processor.audio_chunker import AudioChunker
from ..processor.text_merger import TextMerger

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/webp', 'image/heic', 'image/heif',
}


def compress_and_convert_image(input_path: str, target_size=1 * 1024 * 1024):  # 2MB default target
    """
    Compress and convert image files to PNG format using ffmpeg.

    Args:
        input_path (str): Path to the original image file
        target_size (int, optional): Target file size in bytes. Defaults to 2MB

    Returns:
        str: Path to the temporary compressed/converted PNG file

    Raises:
        RuntimeError: If FFmpeg compression/conversion fails

    Notes:
        - Creates a temporary PNG file that should be deleted after use
        - Compresses images over target_size
        - Uses maximum available CPU threads for faster processing
    """
    temp_dir = os.path.abspath("temp")
    os.makedirs(temp_dir, exist_ok=True)
    tempfile.tempdir = temp_dir
    try:
        # Create temporary file for image output
        fd, temp_image_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)

        # Get original file size
        original_size = os.path.getsize(input_path)
        logger.info(f"Original image size: {original_size / 1024 / 1024:.2f}MB")

        if original_size > target_size:
            # Calculate compression ratio based on target size
            compression_ratio = (target_size / original_size) ** 0.5
            new_size = int(100 * compression_ratio)  # Convert to percentage
            new_size = max(1, min(new_size, 100))  # Ensure between 1-100

            logger.info(f"Compressing image to {new_size}% quality")
            ffmpeg.input(input_path).output(
                temp_image_path,
                vf=f'scale=iw*{compression_ratio}:ih*{compression_ratio}',  # Scale dimensions
                compression_level=9,  # Maximum PNG compression
                threads=0,  # Use maximum available threads
                loglevel='error'  # Reduce logging overhead
            ).run(quiet=True, overwrite_output=True)
        else:
            # Just convert to PNG if no compression needed
            logger.info("Converting image to PNG without compression")
            ffmpeg.input(input_path).output(
                temp_image_path,
                compression_level=9,
                threads=0,
                loglevel='error'
            ).run(quiet=True, overwrite_output=True)

        logger.info(f"Successfully processed image: {temp_image_path}")
        return temp_image_path

    except Exception as e:
        raise RuntimeError(f"FFmpeg error during image processing: {e}") from e

def get_full_ocr(audio_file, markdown_output=False, llm_api_key=None):
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
    converter = OCRToTextConverter(markdown_output=markdown_output, llm_api_key=llm_api_key)
    return converter.get_full_ocr(audio_file)

class OCRToTextConverter:
    def __init__(self, ocr_model="gemini-2.0-flash", ocr_model_provider="google",
                markdown_output=True, llm_api_key=None, max_llm_tokens=8000, temp_dir="temp"):
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
        self.ocr_model = ocr_model
        self.ocr_model_provider = ocr_model_provider
        self.markdown_output = markdown_output
        self.llm_api_key = llm_api_key
        self.max_llm_tokens = max_llm_tokens

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
    def get_ocr(self, files_for_ocr):
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
            prompt_template = OCR_TO_MARKDOWN_PROMPT
        else:
            logger.info("Using prompt for plain text format")
            # Convert the text to plain text format
            prompt_template = OCR_TO_PLAIN_TEXT_PROMPT

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

            total_size = 0
            new_files_for_ocr = []
            for file_for_ocr in files_for_ocr:
                file_for_ocr = compress_and_convert_image(file_for_ocr)
                file_size = os.path.getsize(file_for_ocr)
                total_size += file_size
                new_files_for_ocr.append(file_for_ocr)

            logger.info(f"Total file size: {total_size / (1024 * 1024):.2f} MB")
            logger.info(f"new_files_for_ocr: {new_files_for_ocr}")

            if total_size > 2 * 1024 * 1024:
                logger.info("Total image file size exceeds 20MB, uploading file before transcription")

                myfiles = []
                for file_for_ocr in new_files_for_ocr:
                    myfile = client.files.upload(file=file_for_ocr)
                    myfiles.append(myfile)

                logger.info(f"Uploaded {len(myfiles)} images files - Starting OCR...")

                contents = [prompt_template]
                for myfile in myfiles:
                    contents.append(myfile)
                response = client.models.generate_content(
                    model=self.ocr_model,
                    contents=contents,
                    config=config
                )

                for myfile in myfiles:
                    client.files.delete(name=myfile.name)

            else:
                logger.info("Total image file size does not exceed 20MB")
                images_data = []
                for file_for_ocr in new_files_for_ocr:
                    with open(file_for_ocr, "rb") as f:
                        image_data = f.read()
                        images_data.append(image_data)

                # Determine mimetype
                mime_type, _ = mimetypes.guess_type(new_files_for_ocr[0])
                if mime_type is None:
                    raise ValueError("Image format not recognized")

                contents = []
                if prompt_template:
                    contents.append(prompt_template)
                for image_data in images_data:
                    # contents.append({"mime_type": mime_type, "data": image_data})
                    contents.append(types.Part.from_bytes(
                            data=image_data,
                            mime_type=mime_type,
                        ))

                response = client.models.generate_content(
                    model=self.ocr_model,
                    contents=contents,
                    config=config
                )

            logger.info(f"OCR response: {response}")
            end_time = time.time()
            time_elapsed = end_time - start_time

            logger.info(f"Completion tokens: {response.usage_metadata.candidates_token_count}")
            logger.info(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")

            response_dict = {"transcript": response.text,
                             "completion_tokens": response.usage_metadata.candidates_token_count,
                             "prompt_tokens": response.usage_metadata.prompt_token_count}

            logger.info(f"Transcribed text using {self.ocr_model} in {time_elapsed:.2f} seconds")
            return response_dict

        except Exception as e:
            logger.error(f"Error during ocr processing: {str(e)}")
            raise

    def process_chunk(self, chunk, index):
        """Process a single audio chunk and return its transcript"""
        logger.info(f"Transcribing chunk {index + 1}...")
        transcript_dict = self.transcribe_audio(chunk["file_path"])
        transcript = transcript_dict["transcript"]

        return index, transcript_dict

    def get_full_ocr(self, image_list):
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

