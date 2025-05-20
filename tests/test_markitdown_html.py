import os
import sys
import logging

from polytext.loader import HtmlLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

url = 'https://it.wikipedia.org/wiki/Diritto_privato'
    # 'https://www.youmath.it/domande-a-risposte/view/5393-integrale-cos2x.html'

def main():
        html_loader = HtmlLoader(is_text=True)

        try:
            result = html_loader.get_text_from_url(url=url)
            return result
        except Exception as e:
            logging.error(f"Error extracting markdown or plain text: {str(e)}")

if __name__ == "__main__":
    main()