import unittest

from polytext.loader.base import BaseLoader
from polytext.utils import utils


class TestExtractedTextWhitespace(unittest.TestCase):
    def test_clean_extracted_text_whitespace_preserves_heading_and_paragraphs(self):
        cleaner = getattr(utils, "clean_extracted_text_whitespace", lambda text: text)

        raw_text = "  # Title  \nThis is a line with\nartifact   spaces.\n\n\nNext paragraph.\n"

        self.assertEqual(
            cleaner(raw_text),
            "# Title\nThis is a line with artifact spaces.\n\nNext paragraph.",
        )

    def test_run_loader_class_applies_markdown_strip_and_whitespace_cleanup(self):
        class _StubLoader:
            @staticmethod
            def load(input_path):
                return {
                    "text": "```markdown\n# Title  \nThis sentence\ncontinues.\n```",
                    "completion_tokens": 4,
                    "prompt_tokens": 2,
                }

        loader = BaseLoader(source="local")

        result = loader.run_loader_class(loader_class=_StubLoader(), input_list=["/tmp/example.txt"])

        self.assertEqual(result["text"], "# Title\nThis sentence continues.")
        self.assertEqual(result["output_list"][0]["text"], "# Title\nThis sentence continues.")

    def test_clean_extracted_text_whitespace_keeps_newline_after_sentence_end(self):
        cleaner = getattr(utils, "clean_extracted_text_whitespace", lambda text: text)

        raw_text = "First sentence.\nSecond sentence starts here."

        self.assertEqual(
            cleaner(raw_text),
            "First sentence.\nSecond sentence starts here.",
        )

    def test_clean_extracted_text_whitespace_keeps_heading_on_its_own_line(self):
        cleaner = getattr(utils, "clean_extracted_text_whitespace", lambda text: text)

        raw_text = "Intro line\n# Heading\nBody text continues here."

        self.assertEqual(
            cleaner(raw_text),
            "Intro line\n# Heading\nBody text continues here.",
        )
