import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv('..env')

from polytext.loader.base import BaseLoader

url = 'https://www.youtube.com/watch?v=Md4Fs-Zc3tg&t=173s'
# 'https://www.youtube.com/watch?v=xY5x0q5JoPI'
# 'https://www.youtube.com/watch?v=6Ql5mQdxeWk'
# 'https://www.youtube.com/watch?v=Md4Fs-Zc3tg&t=173s'
# 'https://www.youtube.com/watch?v=xY5x0q5JoPI'

def main():
    markdown_output = True
    save_transcript_chunks = True

    loader = BaseLoader(
        markdown_output=markdown_output,
        save_transcript_chunks=save_transcript_chunks
    )

    try:
        result_dict = loader.get_text(
            input_list=[url]
        )
        return result_dict

    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")

if __name__ == "__main__":
    main()