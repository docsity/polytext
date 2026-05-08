import os
import sys
import time
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv('..env')

from polytext.loader.base import BaseLoader

# url = 'https://www.youtube.com/watch?v=FvfsFk2p1J0'
# private 'https://www.youtube.com/watch?v=y0JSaif7DRU'
# 'https://www.youtube.com/watch?v=xY5x0q5JoPI'
# 'https://www.youtube.com/watch?v=6Ql5mQdxeWk'
# url = 'https://www.youtube.com/watch?v=Md4Fs-Zc3tg' #&t=173s'
# 'https://www.youtube.com/watch?v=w82a1FT5o88'
# no parole https://www.youtube.com/watch?v=SGT1mvdfLeU
# age restricted https://www.youtube.com/watch?v=l_pmZOlJUu4

url = 'https://www.youtube.com/watch?v=Uux6F3C-7Xk'  # barbero 80 minuti, OK in 273 secondi con gemini-3-flash-preview (443k token in input, 16k in output)

url = 'https://www.youtube.com/watch?v=L4as3tks4Js'  # basement alberto angela  ERRORE REPETITIONS con gemini-2.5-flash  (590k token in input, 8k in output)

# url = 'https://www.youtube.com/watch?v=UabBYexBD4k'  # INM RAG 11 minuti, completato in 26 secondi con successo con gemini-3.1-flash-lite

# url = 'https://www.youtube.com/watch?v=96jN2OCOfLs'  # Vibe coding 30 minuti, completato in 150 secondi con successo con gemini-3-flash-preview (160k token in input, 7k in output), 3.1-flash-lite ha raggiunto i max tokens in output (50k) probabile repetition

url = 'https://www.youtube.com/watch?v=HGfsGvmRaaw'  # barbero2 50 minuti, fallito, RECITATION in tutti e 3 i modelli (275k token in input)

url = 'https://www.youtube.com/watch?v=CM2CkNU9xR0'  # google antigravity 27 minuti, completato in 39 secondi con successo con gemini-3.1-flash-lite (146k token in input, 6k token in output)

def main():
    markdown_output = True
    save_transcript_chunks = True
    timeout_minutes = int(os.getenv("YOUTUBE_TRANSCRIPT_TIMEOUT_MINUTES", "15"))

    loader = BaseLoader(
        markdown_output=markdown_output,
        save_transcript_chunks=save_transcript_chunks,
        timeout_minutes=timeout_minutes
    )

    start = time.time()
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("Using YouTube transcript timeout: %s minutes", timeout_minutes)
    result_dict = loader.get_text(
        input_list=[url]
    )
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    end = time.time()
    print("Time elapsed: ", end - start)
    print(result_dict)
    return result_dict

if __name__ == "__main__":
    main()
