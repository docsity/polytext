import os
import sys
import logging
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.loader.base import BaseLoader

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    markdown_output = True
    save_transcript_chunks = True
    source = "local"
    bitrate_quality = 8

    # Initialize BaseLoader
    loader = BaseLoader(
        source=source,
        markdown_output=markdown_output,
        save_transcript_chunks = save_transcript_chunks,
        bitrate_quality = bitrate_quality,
        timeout_minutes=1
    )

    # Define document data
    file_path = "gcs://opit-da-test-ml-ai-store-bucket/learning_resources/course_id=406/module_id=2658/id=31427/8434.mp4"

    local_file_path = "/Users/marcodelgiudice/Projects/polytext/1757923647_audio.m4a"

    # Call get_text method
    start = time.time()
    result_dict = loader.get_text(
        input_list=[local_file_path],
    )
    end = time.time()
    print("Time elapsed: ", end - start)

    import ipdb; ipdb.set_trace()

    try:
        output_file = "audio_8_barbero_0_5_ore.md" if markdown_output else "transcript.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result_dict["text"])
        print(f"Transcript saved to {output_file}")
    except IOError as e:
        logging.error(f"Failed to save transcript: {str(e)}")

    # print(f"Successfully extracted text ({len(document_text)} characters)")
    # #print("Sample of extracted text:")
    # #print(document_text[:500] + "...")  # Print first 500 chars
    #
    # # Optionally save the extracted text to a file
    # with open("extracted_text.txt", "w", encoding="utf-8") as f:
    #     f.write(document_text)


if __name__ == "__main__":
    main()