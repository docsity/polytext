# processor/text_merger.py
import re
import logging
from retry import retry
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.api_core import exceptions as google_exceptions

from ..prompts.text_merging import TEXT_MERGE_PROMPT

logger = logging.getLogger(__name__)

class TextMerger:
    def __init__(self, completion_model="gemini-2.0-flash", completion_model_provider="google",
                 llm_api_key=None, max_llm_tokens=8000, k=5, min_matches=3, n_words_for_llm_merge=200):
        self.completion_model = completion_model
        self.completion_model_provider = completion_model_provider
        self.k = k
        self.min_matches = min_matches
        self.llm_api_key = llm_api_key
        self.max_llm_tokens = max_llm_tokens
        self.n_words_for_llm_merge = n_words_for_llm_merge

    def merge_texts(self, text1, text2):
        """
        Merge two texts by finding where they overlap and combining them.

        Args:
            text1 (str): The first text (beginning part)
            text2 (str): The second text (ending part)

        Returns:
            str: The merged text, or original texts concatenated if no good merge point found
        """
        # Clean and split the texts into words
        import re

        def clean_and_split(text):
            # Convert to lowercase and split by whitespace
            return re.findall(r'\b\w+\b', text.lower())

        words1 = clean_and_split(text1)
        words2 = clean_and_split(text2)

        if len(words2) < self.k or len(words1) < self.k:
            return text1 + " " + text2  # Texts too short for meaningful merge

        # Get the first k words of text2
        search_words = words2[:self.k]

        # Maximum number of words to check in text1 (last k+20 words)
        check_length = min(len(words1), self.k + 20)

        best_match_count = 0
        best_match_position = -1

        # Check each possible position in the last part of text1
        for i in range(max(0, len(words1) - check_length), len(words1) - self.k + 1):
            matches = 0
            for j in range(self.k):
                if i + j < len(words1) and words1[i + j] == search_words[j]:
                    matches += 1

            if matches > best_match_count:
                best_match_count = matches
                best_match_position = i

        # If we found enough matching words, perform the merge
        if best_match_count >= self.min_matches and best_match_position != -1:
            # Find the position in the original text1 that corresponds to best_match_position
            # We need to map from word index to character index
            char_position = 0
            word_count = 0

            for m in re.finditer(r'\b\w+\b', text1.lower()):
                if word_count == best_match_position:
                    char_position = m.start()
                    break
                word_count += 1

            # Get all of text1 up to the match point
            merged_text = text1[:char_position]

            # Add text2 content from after the matching section
            # We're being cautious here, keeping k words and then adding the rest
            merged_text += " " + text2

            return merged_text

        # If no good merge found, just concatenate the texts
        return text1 + " " + text2

    def merge_chunks(self, chunks):
        """
        Merge an ordered list of text chunks into a single document.

        Parameters
        ----------
        chunks : list[str]
            [chunk_1, chunk_2, …] in their natural order.

        Returns
        -------
        str
            One continuous piece of text produced by repeatedly calling
            `merge_texts` on successive pairs:
            result = merge_texts(chunk_1, chunk_2)
            result = merge_texts(result,  chunk_3)
            …
        """
        if not chunks:                     # Handle an empty list gracefully
            return ""

        merged = chunks[0]
        for nxt in chunks[1:]:
            merged = self.merge_texts(merged, nxt)
        return merged


    @staticmethod
    def extract_complete_sentences(text, n_words):
        """
        Extract the first N words, central text, and last N words that form complete sentences.

        Args:
            text (str): The input text to process
            n_words (int): Number of words to extract from start and end

        Returns:
            list: [start_text, central_text, end_text] where:
                - start_text (str): The first N words as complete sentences
                - central_text (str): The text between start and end
                - end_text (str): The last N words as complete sentences
        """
        # Split the text into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())

        # Remove any empty sentences
        sentences = [s for s in sentences if s.strip()]

        if not sentences:
            return ["", "", ""]

        # Process sentences from the beginning
        start_sentences = []
        start_word_count = 0
        start_idx = 0

        for i, sentence in enumerate(sentences):
            words = sentence.split()
            if start_word_count + len(words) <= n_words:
                start_sentences.append(sentence)
                start_word_count += len(words)
                start_idx = i + 1
            else:
                break

        # Process sentences from the end
        end_sentences = []
        end_word_count = 0
        end_idx = len(sentences)

        for i, sentence in enumerate(reversed(sentences)):
            words = sentence.split()
            if end_word_count + len(words) <= n_words:
                end_sentences.insert(0, sentence)
                end_word_count += len(words)
                end_idx = len(sentences) - i - 1
            else:
                break

        # Extract the three parts
        start_text = " ".join(start_sentences)
        central_text = " ".join(sentences[start_idx:end_idx])
        end_text = " ".join(end_sentences)

        return [start_text, central_text, end_text]


    @retry(
        (
                google_exceptions.DeadlineExceeded,
                google_exceptions.ResourceExhausted,
                google_exceptions.ServiceUnavailable,
                google_exceptions.InternalServerError
        ),
        tries=8,
        delay=1,
        backoff=2,
        logger=logger,
    )
    def merge_texts_with_llm(self, text1, text2):
        """
        Merge two texts using a language model to ensure coherence and fluency.

        Args:
            text1 (str): The first text (beginning part)
            text2 (str): The second text (ending part)

        Returns:
            str: The merged text
        """

        [start_text_1, central_text_1, end_text_1] = self.extract_complete_sentences(text1,
                                                                                     n_words=self.n_words_for_llm_merge)
        [start_text_2, central_text_2, end_text_2] = self.extract_complete_sentences(text2,
                                                                                     n_words=self.n_words_for_llm_merge)

        logger.info("Extracted complete sentences for merging")

        try:
            if self.llm_api_key:
                logger.info("Using provided Google API key")
                client = genai.Client(api_key=self.llm_api_key)
            else:
                logger.info("Using Google API key from ENV")
                client = genai.Client()

            config = types.GenerateContentConfig(
                # temperature=0,
                safety_settings=[
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                ]
            )

            prompt = TEXT_MERGE_PROMPT.format(text_1=end_text_1, text_2=start_text_2)

            response = client.models.generate_content(
                model=self.completion_model,
                contents=prompt,
                config=config
            )

            logger.info(f"Completion tokens: {response.usage_metadata.candidates_token_count}")
            logger.info(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")

            response_dict = {"completion_tokens": response.usage_metadata.candidates_token_count,
                             "prompt_tokens": response.usage_metadata.prompt_token_count,
                             "start_text_1": start_text_1,
                             "central_text_1": central_text_1,
                             "merged_text": response.text,
                             "central_text_2": central_text_2,
                             "end_text_2": end_text_2}

            logger.info("Texts merged with LLM")
            return response_dict

        except Exception as e:
            logger.error(f"Error during text merging: {str(e)}")
            raise


    def merge_chunks_with_llm_sequential(self, chunks):
        """
        Merge chunks using LLM sequentially.

        Args:
            chunks (list): List of text chunks to merge

        Returns:
            dict:
                - full_text_merged (str): The complete merged text
                - completion_tokens (int): Total completion tokens used
                - prompt_tokens (int): Total prompt tokens used
        """
        if not chunks:
            return {"full_text_merged": "", "completion_tokens": 0, "prompt_tokens": 0}

        if len(chunks) == 1:
            return {"full_text_merged": chunks[0], "completion_tokens": 0, "prompt_tokens": 0}

        merged_chunks = {}
        completion_tokens = 0
        prompt_tokens = 0

        merged_text = chunks[0]
        for i in range(len(chunks) - 1):
            logger.info(f"Processing chunk pair {i + 1}...")
            merged_text_dict = self.merge_texts_with_llm(merged_text, chunks[i + 1])
            merged_text = merged_text_dict["start_text_1"] + " " + merged_text_dict["central_text_1"] + " " + \
                          merged_text_dict["merged_text"] + " " + merged_text_dict["central_text_2"] + " " + \
                          merged_text_dict["end_text_2"]
            completion_tokens += merged_text_dict["completion_tokens"]
            prompt_tokens += merged_text_dict["prompt_tokens"]

        return {
            "full_text_merged": merged_text,
            "completion_tokens": completion_tokens,
            "prompt_tokens": prompt_tokens
        }


    def process_chunk_pair(self, chunk_pair, index):
        """Process a couple of chunks and return their merged text."""
        logger.info(f"Processing chunk pair {index + 1}...")
        merged_text_dict = self.merge_texts_with_llm(chunk_pair[0], chunk_pair[1])

        return index, merged_text_dict


    def merge_chunks_with_llm(self, chunks):
        """
        Merge chunks using LLM in parallel.

        Args:
            chunks (list): List of text chunks to merge

        Returns:
            dict:
                - full_text_merged (str): The complete merged text
                - completion_tokens (int): Total completion tokens used
                - prompt_tokens (int): Total prompt tokens used
        """
        if not chunks:
            return {"full_text_merged": "", "completion_tokens": 0, "prompt_tokens": 0}

        if len(chunks) == 1:
            return {"full_text_merged": chunks[0], "completion_tokens": 0, "prompt_tokens": 0}

        chunk_pairs = [(chunks[i], chunks[i + 1]) for i in range(len(chunks) - 1)]
        merged_chunks = {}

        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self.process_chunk_pair, pair, i): i for i, pair in enumerate(chunk_pairs)}

            completion_tokens = 0
            prompt_tokens = 0
            for future in as_completed(futures):
                index, merged_text_dict = future.result()
                merged_chunks[index] = merged_text_dict
                completion_tokens += merged_text_dict["completion_tokens"]
                prompt_tokens += merged_text_dict["prompt_tokens"]
                logger.info(f"Chunk pair {index + 1} merged successfully.")

            full_text_merged = ""
            for i in range(len(merged_chunks)):
                if i == 0:
                    full_text_merged = " ".join([
                        merged_chunks[i]["start_text_1"],
                        merged_chunks[i]["central_text_1"],
                        merged_chunks[i]["merged_text"]
                    ])
                elif i == len(merged_chunks) - 1:
                    full_text_merged += " " + " ".join([
                        merged_chunks[i]["central_text_1"],
                        merged_chunks[i]["merged_text"],
                        merged_chunks[i]["central_text_2"],
                        merged_chunks[i]["end_text_2"]
                    ])
                else:
                    full_text_merged += " " + " ".join([
                        merged_chunks[i]["central_text_1"],
                        merged_chunks[i]["merged_text"]
                    ])

        return {
            "full_text_merged": full_text_merged.strip(),
            "completion_tokens": completion_tokens,
            "prompt_tokens": prompt_tokens
        }
