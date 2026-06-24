import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

from polytext.loader.base import BaseLoader

load_dotenv("..env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("polytext")


PLAIN_TEXT_SAMPLE = """"""


def run_beautiful_text(input_value: str, source: str = "local", activate_full_process: bool = False) -> dict:
    loader = BaseLoader(
        markdown_output=True,
        save_transcript_chunks=True,
        source=source,
    )
    result_dict_original = None
    if activate_full_process:
        local_file_path = "/Users/username/Projects/polytext/mk5konma-f4c711ba3480d81e35d60ddee5cea1cf15c690d6.mp4" #  "s3://docsity-data/documents/original/2011/06/05/La_disciplina_degli_enti_locali_negli_statuti_regionali.pdf"  # "https://www.youtube.com/watch?v=Njrr5etGFGg&list=PLufwFtblC0Rta8GZlxVJ7DWqVnrENbrCV&index=4" # "/Users/andreasolfanelli/Projects/polytext/giovedì alle 10-15(2).aac"

        logger.info("FULL PROCESS ACTIVE - using local file path: %s", local_file_path)
        result_dict_original = loader.get_text(input_list=[local_file_path])
        logger.info("***** END FULL PROCESS ACTIVE ******")
        print(result_dict_original)

    result_dict = loader.get_beautiful_text(input_list=[result_dict_original["text"] if activate_full_process else input_value], active_chapters=True)

    logger.info("Input: %s", input_value)
    logger.info("Type: %s", result_dict.get("type"))
    logger.info("Completion model: %s", result_dict.get("completion_model"))
    logger.info("Completion tokens: %s", result_dict.get("completion_tokens"))
    logger.info("Prompt tokens: %s", result_dict.get("prompt_tokens"))
    logger.info("Preview:\n%s", result_dict.get("text", "")[:2000])

    return result_dict


def main():
    mode = "full_process"

    if mode == "plain_text":
        return run_beautiful_text(PLAIN_TEXT_SAMPLE, source="local")

    if mode == "local_file":
        local_file_path = "/Users/username/Projects/polytext/summary_note_64_84_level_1_develop_type_G20Y40.pdf" # "/Users/andreasolfanelli/Projects/polytext/2.-Principi-fondamentali.pdf" # "/Users/andreasolfanelli/Projects/polytext/1.materiale del'istituto Lezione-2_La-norma-giuridica--caratteristiche-e-interpretazione--e-sanzioni.pdf"
        return run_beautiful_text(local_file_path, source="local")

    if mode == "s3_file":
        s3_file_path = "s3://docsity-data/documents/original/2011/06/05/La_disciplina_degli_enti_locali_negli_statuti_regionali.pdf" # "s3://docsity-ai-develop/da_ml_ai_summary_output/lang=it/y=2026/m=05/d=12/upload_date=2026-05-12/summary_note_70_96_level_1_develop_type_G20Y40.pdf"
        return run_beautiful_text(s3_file_path, source="cloud")

    if mode == "full_process":
        return run_beautiful_text("", source="local", activate_full_process=True)

    raise ValueError(f"Unsupported mode: {mode}")


if __name__ == "__main__":
    main()
