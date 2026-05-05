import unittest
import importlib.util
from pathlib import Path


_UTILS_PATH = Path(__file__).resolve().parents[1] / "polytext" / "utils" / "utils.py"
_SPEC = importlib.util.spec_from_file_location("polytext_utils_utils", _UTILS_PATH)
utils = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(utils)


class TestExtractedTextWhitespace(unittest.TestCase):
    def test_clean_extracted_text_whitespace_preserves_heading_and_paragraphs(self):
        cleaner = getattr(utils, "clean_extracted_text_whitespace", lambda text: text)

        raw_text = "  # Title  \nThis is a line with\nartifact   spaces.\n\n\nNext paragraph.\n"

        self.assertEqual(
            cleaner(raw_text),
            "# Title\nThis is a line with artifact spaces.\n\nNext paragraph.",
        )

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

    def test_clean_extracted_text_whitespace_splits_inline_markdown_heading(self):
        cleaner = getattr(utils, "clean_extracted_text_whitespace", lambda text: text)

        raw_text = "Prima frase conclusa. ## Discussione sulla Home Page"

        self.assertEqual(
            cleaner(raw_text),
            "Prima frase conclusa.\n## Discussione sulla Home Page",
        )
