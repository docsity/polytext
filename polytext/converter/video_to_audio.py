# converter/video_to_audio.py
import os
import tempfile
import ffmpeg
import logging

logger = logging.getLogger(__name__)

def convert_video_to_audio(video_file: str , bitrate_quality: int =9) -> str:
    """
    Convert a video file to audio format using ffmpeg-python.

    Args:
        video_file (str): Path to the video file.
        bitrate_quality (int, optional): Retained for backward compatibility; WAV output is lossless.

    Returns:
        str: Path to the converted audio file.

    Raises:
        ffmpeg.Error: If FFmpeg conversion fails
        Exception: If any other error occurs during conversion
    """

    logger.info("Converting video to lossless 16 kHz mono WAV.")

    temp_audio_path = None
    try:
        # Create temporary file for audio output
        fd, temp_audio_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

        # Simple efficient pipeline
        (
            ffmpeg
            .input(video_file)
            .output(temp_audio_path,
                    acodec='pcm_s16le',
                    ac=1,  # Convert to mono
                    ar=16000,  # Lower sample rate
                    vn=None,
                    threads=0,  # Use maximum available threads
                    loglevel='error',  # Reduce logging overhead
                    )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        logger.info(f"Successfully converted video to audio: {temp_audio_path}")
        return temp_audio_path

    except ffmpeg.Error as e:
        logger.exception("FFmpeg conversion failed: %s", e.stderr.decode())
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)
        raise
    except Exception as e:
        logger.exception("Failed to convert video to audio: %s", str(e))
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)
        raise
