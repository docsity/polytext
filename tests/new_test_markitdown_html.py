import os
import sys
import logging

from polytext.loader import BaseLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

url = 'https://it.wikipedia.org/wiki/Diritto_privato'
    # 'https://www.youmath.it/domande-a-risposte/view/5393-integrale-cos2x.html'

def main():
        loader = BaseLoader()
        markdown_output = True

        try:
            result_dict = loader.get_text(input_list=[url], markdown_output=markdown_output)
            return result_dict
        except Exception as e:
            logging.error(f"Error extracting markdown or plain text: {str(e)}")

if __name__ == "__main__":
    main()