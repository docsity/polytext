# processor/transcript_chunker.py

from typing import List, Dict


class TranscriptChunker:
    """
    Splits a long transcript into overlapping character-based chunks suitable for LLM processing.
    """

    def __init__(
        self,
        transcript: str,
        max_llm_tokens: int = 8000,
        prompt_overhead: int = 1000,
        tokens_per_char: float = 0.25,
        overlap_chars: int = 500
    ):
        """
        Initialize the TranscriptChunker.

        Args:
            transcript (str): The full transcript to be chunked.
            max_llm_tokens (int, optional): Maximum number of tokens the LLM can handle. Defaults to 8000.
            prompt_overhead (int, optional): Number of tokens reserved for the prompt. Defaults to 1000.
            tokens_per_char (float, optional): Estimated average number of tokens per character. Defaults to 0.25.
            overlap_chars (int, optional): Number of characters to overlap between consecutive chunks. Defaults to 500.
        """
        self.transcript = transcript
        self.max_llm_tokens = max_llm_tokens
        self.prompt_overhead = prompt_overhead
        self.tokens_per_char = tokens_per_char
        self.overlap_chars = overlap_chars

        self.max_chars_per_chunk = int((self.max_llm_tokens - self.prompt_overhead) / self.tokens_per_char)

    def chunk_transcript(self) -> List[Dict[str, any]]:
        """
        Split the transcript into overlapping character-based chunks for LLM input.

        The chunking ensures that each chunk respects the token limits and attempts to end at sentence boundaries.

        Returns:
            List[Dict[str, any]]: A list of dictionaries containing:
                - index (int): Index of the chunk.
                - start_char (int): Start character index in the original transcript.
                - end_char (int): End character index in the original transcript.
                - text (str): The actual text of the chunk.
        """
        text = self.transcript
        total_chars = len(text)

        chunks = []
        start = 0
        index = 0

        while start < total_chars:
            end = min(start + self.max_chars_per_chunk, total_chars)
            chunk_text = text[start:end]

            # Try to extend to the end of the current sentence, if possible
            if end < len(text):
                extra = text[end:]
                sentence_end = extra.find(".")
                if sentence_end != -1:
                    # Include up to the period (inclusive)
                    chunk_text = text[start:end + sentence_end + 1]
                    end = end + sentence_end + 1

            chunks.append({
                "index": index,
                "start_char": start,
                "end_char": end,
                "text": chunk_text
            })

            if end == total_chars:
                break
            else:
                index += 1
                start = end - self.overlap_chars  # Start next chunk with overlap

        return chunks