import os
import sys
import logging

from polytext.loader.base import BaseLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

url = 'https://it.wikipedia.org/wiki/Termodinamica'
    # 'https://www.youmath.it/domande-a-risposte/view/5393-integrale-cos2x.html'

def main():
    markdown_output = True

    loader = BaseLoader(markdown_output=markdown_output)

    try:
        result_dict = loader.get_text(input_list=[url])

        with open("md_2_medium.md", "w", encoding="utf-8") as f:
            f.write(result_dict['text'])

        return result_dict

    except Exception as e:
        raise RuntimeError(f"Error extracting markdown or plain text: {str(e)}")

if __name__ == "__main__":
    result = main()

import ipdb; ipdb.set_trace()