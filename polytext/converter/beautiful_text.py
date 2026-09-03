import logging
import re
import time
from importlib import import_module

from google.api_core import exceptions as google_exceptions
from retry import retry
from concurrent.futures import ThreadPoolExecutor, as_completed

from polytext.prompts.beautiful_text import BEAUTIFUL_TEXT_PROMPT
from polytext.llm import MultimodalLLM

logger = logging.getLogger(__name__)


class BeautifulTextConverter:
    """Clean and structure extracted text using Google Gemini or OpenAI."""

    def __init__(
        self,
        llm_api_key: str = None,
        model: str = "gemini-3.1-flash-lite",
        model_provider: str = "google",
        max_llm_tokens: int = 8000,
        prompt_overhead: int = 1800,
        tokens_per_char: float = 0.25,
        overlap_chars: int = 800,
        max_target_chars: int = 12000,
    ) -> None:
        """Configure chunking and the LLM used to clean extracted text.

        ``llm_api_key`` overrides provider environment configuration. When it
        is omitted, the selected SDK resolves its standard environment
        variables, such as ``OPENAI_API_KEY`` for direct OpenAI.
        """
        self.llm_api_key = llm_api_key
        self.model = model
        self.model_provider = model_provider
        self.max_llm_tokens = max_llm_tokens
        self.prompt_overhead = prompt_overhead
        self.tokens_per_char = tokens_per_char
        self.overlap_chars = overlap_chars
        self.max_target_chars = max_target_chars

    def get_client(self):
        """Return a provider-neutral adapter configured for text generation."""
        return MultimodalLLM(
            model=self.model,
            provider=self.model_provider,
            api_key=self.llm_api_key,
        )

    def chunk_raw_text(self, raw_text: str) -> list[dict]:
        text = (raw_text or "").strip()
        if not text:
            return []

        chunks = []
        start = 0
        index = 0

        while start < len(text):
            proposed_end = min(start + self.max_target_chars, len(text))
            end = self._find_chunk_end(text, start, proposed_end)
            target_text = text[start:end].strip()

            if not target_text:
                break

            chunks.append(
                {
                    "index": index,
                    "target_text": target_text,
                }
            )
            start = end
            index += 1

        return chunks

    def _find_chunk_end(self, text: str, start: int, proposed_end: int) -> int:
        if proposed_end >= len(text):
            return len(text)

        minimum_end = start + int(self.max_target_chars * 0.65)
        chunk_window = text[minimum_end:proposed_end]
        sentence_boundaries = list(re.finditer(r"(?<=[.!?])\s+", chunk_window))
        if sentence_boundaries:
            return minimum_end + sentence_boundaries[-1].end()

        paragraph_boundary = text.rfind("\n\n", minimum_end, proposed_end)
        if paragraph_boundary != -1:
            return paragraph_boundary + 2

        whitespace_boundary = text.rfind(" ", minimum_end, proposed_end)
        if whitespace_boundary != -1:
            return whitespace_boundary + 1

        return proposed_end

    @retry(
        (
            google_exceptions.DeadlineExceeded,
            google_exceptions.ResourceExhausted,
            google_exceptions.ServiceUnavailable,
            google_exceptions.InternalServerError,
        ),
        tries=5,
        delay=2,
        backoff=2,
        logger=logger,
    )
    def process_chunk(self, client, chunk: dict, index: int) -> dict:
        logger.info("Processing beautiful text chunk %s", index + 1)
        start_time = time.time()

        target_text = chunk["target_text"]

        response = client.generate_text(
            instructions=BEAUTIFUL_TEXT_PROMPT,
            input_text=f"TARGET TEXT TO CLEAN\n{target_text}",
            max_output_tokens=self.max_llm_tokens,
        )

        logger.info("Beautiful text chunk %s processed in %.2fs", index + 1, time.time() - start_time)

        return {
            "transcript": response.text,
            "completion_tokens": response.completion_tokens,
            "prompt_tokens": response.prompt_tokens,
        }

    def merge_cleaned_chunks(self, chunks: list[str]) -> str:
        return "\n\n".join(chunk.strip() for chunk in chunks if chunk.strip())

    def _convert_markdown_to_json(self, markdown_text: str) -> dict:
        if not markdown_text.strip():
            return {}

        try:
            markdown_to_json = import_module("markdown_to_json")
        except ImportError as exc:
            raise ImportError(
                "markdown-to-json is required when active_chapters=True. "
                "Install it with: pip install markdown-to-json"
            ) from exc

        return markdown_to_json.dictify(markdown_text)

    def _build_chapters(self, markdown_text: str) -> list[dict]:
        heading_pattern = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
        chapters = []
        stack: list[dict] = []

        def finalize_nodes(target_depth: int = 0) -> None:
            while len(stack) > target_depth:
                node_state = stack.pop()
                node_state["node"]["content"] = "\n".join(node_state["content_lines"]).strip()

        for line in markdown_text.splitlines():
            heading_match = heading_pattern.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                while stack and stack[-1]["node"]["level"] >= level:
                    finalize_nodes(len(stack) - 1)

                chapter_node = {
                    "title": title,
                    "level": level,
                    "content": "",
                    "children": [],
                }

                if stack:
                    stack[-1]["node"]["children"].append(chapter_node)
                else:
                    chapters.append(chapter_node)

                stack.append({"node": chapter_node, "content_lines": []})
                continue

            if stack:
                stack[-1]["content_lines"].append(line)

        finalize_nodes()
        return chapters

    def convert(self, raw_text: str, save_transcript_chunks: bool = False, active_chapters: bool = True) -> dict:
        cleaned_input = (raw_text or "").strip()
        if not cleaned_input:
            result = {
                "text": "",
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "completion_model": self.model,
                "completion_model_provider": self.model_provider,
                "text_chunks": [] if save_transcript_chunks else "not provided",
            }
            if active_chapters:
                result["markdown_json"] = {}
                result["chapters"] = []
            return result

        chunks = self.chunk_raw_text(cleaned_input)
        client = self.get_client()

        results = []
        total_completion_tokens = 0
        total_prompt_tokens = 0

        with ThreadPoolExecutor() as executor:
            future_to_index = {
                executor.submit(self.process_chunk, client, chunk, chunk["index"]): chunk["index"]
                for chunk in chunks
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                result = future.result()
                results.append((index, result["transcript"]))
                total_completion_tokens += result["completion_tokens"]
                total_prompt_tokens += result["prompt_tokens"]

        cleaned_chunks = [text for index, text in sorted(results, key=lambda item: item[0])]
        final_text = self.merge_cleaned_chunks(cleaned_chunks)

        result = {
            "text": final_text,
            "completion_tokens": total_completion_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_model": self.model,
            "completion_model_provider": self.model_provider,
            "text_chunks": cleaned_chunks if save_transcript_chunks else "not provided",
        }
        if active_chapters:
            # result["markdown_json"] = self._convert_markdown_to_json(final_text)
            result["chapters"] = self._build_chapters(final_text)
        return result
