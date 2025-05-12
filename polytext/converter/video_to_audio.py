# converter/video_to_audio.py
import os
import tempfile
import ffmpeg
import logging

logger = logging.getLogger(__name__)

def convert_video_to_audio(video_file):
    """
    Convert a video file to audio format using ffmpeg-python.

    Args:
        video_file (str): Path to the video file.

    Returns:
        str: Path to the converted audio file.

    Raises:
        ffmpeg.Error: If FFmpeg conversion fails
        Exception: If any other error occurs during conversion
    """
    temp_audio_path = None
    try:
        # Create temporary file for audio output
        fd, temp_audio_path = tempfile.mkstemp(suffix='.mp3')
        os.close(fd)

        # Simple efficient pipeline
        (
            ffmpeg
            .input(video_file)
            .output(temp_audio_path, acodec='libmp3lame', ab='128k', vn=None)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        logger.info(f"Successfully converted video to audio: {temp_audio_path}")
        return temp_audio_path

    except ffmpeg.Error as e:
        logger.error(f"FFmpeg conversion failed: {e.stderr.decode()}")
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)
        raise
    except Exception as e:
        logger.error(f"Failed to convert video to audio: {str(e)}")
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)
        raise