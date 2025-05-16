import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv('..env')

from polytext.loader import YoutubeTranscriptLoader

url = 'https://www.youtube.com/watch?v=6Ql5mQdxeWk'
# 'https://www.youtube.com/watch?v=Md4Fs-Zc3tg&t=173s'
# 'https://www.youtube.com/watch?v=xY5x0q5JoPI'

def main():
    markdown_output = True
    save_transcript_chunks = True

    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not google_api_key:
        logging.error("GOOGLE_API_KEY not found in environment variables.")

    youtube_transcript_loader = YoutubeTranscriptLoader(
        llm_api_key=google_api_key,
        save_transcript_chunks=save_transcript_chunks
    )

    try:
        youtube_video_transcript = youtube_transcript_loader.get_text_from_youtube(
            video_url=url,
            markdown_output=markdown_output
        )
        print(youtube_video_transcript)
    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")

if __name__ == "__main__":
    main()