import unittest
from unittest.mock import patch

from polytext.converter.document_ocr_to_text import (
    DocumentOCRToTextConverter,
    get_document_ocr,
)
from polytext.llm import GenerationResult, LLMGenerationError
from polytext.loader.base import BaseLoader
from polytext.loader.document_ocr import DocumentOCRLoader


class _Pixmap:
    def __init__(self, payload):
        self.payload = payload

    def save(self, path):
        with open(path, "wb") as image_file:
            image_file.write(self.payload)


class _Page:
    def __init__(self, payload):
        self.payload = payload

    def get_pixmap(self):
        return _Pixmap(self.payload)


class _Pdf:
    def __init__(self, pages):
        self.pages = pages
        self.closed = False

    def __len__(self):
        return len(self.pages)

    def __getitem__(self, index):
        return self.pages[index]

    def close(self):
        self.closed = True


def _result(text, prompt_tokens, completion_tokens):
    return GenerationResult(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model="gpt-5.6-luna",
        provider="openai",
        finish_reason="completed",
    )


class TestOpenAIDocumentOCR(unittest.TestCase):
    def test_base_loader_routes_forced_document_ocr_to_openai_luna(self):
        base_loader = BaseLoader(
            source="local",
            provider="openai",
            force_ocr=True,
        )

        loader = base_loader.init_loader_class(
            input="/tmp/document.pdf",
            storage_client={},
            llm_api_key=None,
            source="local",
        )

        self.assertIsInstance(loader, DocumentOCRLoader)
        self.assertEqual(loader.ocr_provider, "openai")
        self.assertEqual(loader.ocr_model, "gpt-5.6-luna")

    def test_document_loader_accepts_direct_openai_provider(self):
        loader = DocumentOCRLoader(
            source="local",
            ocr_provider="openai",
            ocr_model="gpt-5.6-luna",
        )

        selected = loader._select_document_ocr_fn()

        self.assertTrue(callable(selected))

    @patch("polytext.converter.document_ocr_to_text.MultimodalLLM")
    @patch("fitz.open")
    def test_openai_document_ocr_function_defaults_to_luna(self, fitz_open, llm_cls):
        fitz_open.return_value = _Pdf([_Page(b"page-one")])
        llm_cls.return_value.generate_text_from_image.return_value = _result("First page", 10, 3)

        result = get_document_ocr(
            document_for_ocr="document.pdf",
            ocr_model_provider="openai",
        )

        self.assertEqual(result["completion_model"], "gpt-5.6-luna")
        llm_cls.assert_called_once_with(
            model="gpt-5.6-luna",
            provider="openai",
            api_key=None,
            timeout_minutes=None,
        )

    @patch("polytext.converter.document_ocr_to_text.MultimodalLLM")
    @patch("fitz.open")
    def test_openai_document_ocr_preserves_page_order_and_tokens(self, fitz_open, llm_cls):
        pdf = _Pdf([_Page(b"page-one"), _Page(b"page-two")])
        fitz_open.return_value = pdf

        def generate_text_from_image(**kwargs):
            if kwargs["image_data"] == b"page-one":
                return _result("First page", 10, 3)
            return _result("Second page", 20, 5)

        llm_cls.return_value.generate_text_from_image.side_effect = generate_text_from_image
        converter = DocumentOCRToTextConverter(
            ocr_model="gpt-5.6-luna",
            ocr_model_provider="openai",
            llm_api_key="explicit-key",
        )

        result = converter.get_document_ocr("document.pdf")

        self.assertLess(result["text"].index("First page"), result["text"].index("Second page"))
        self.assertEqual(result["prompt_tokens"], 30)
        self.assertEqual(result["completion_tokens"], 8)
        self.assertEqual(result["completion_model"], "gpt-5.6-luna")
        self.assertEqual(result["completion_model_provider"], "openai")
        self.assertEqual(result["ocr_failed_pages"], [])
        self.assertTrue(pdf.closed)

    @patch("polytext.converter.document_ocr_to_text.MultimodalLLM")
    @patch("fitz.open")
    def test_openai_document_ocr_records_partial_page_failure(self, fitz_open, llm_cls):
        fitz_open.return_value = _Pdf([_Page(b"page-one"), _Page(b"page-two")])

        def generate_text_from_image(**kwargs):
            if kwargs["image_data"] == b"page-two":
                raise LLMGenerationError("OpenAI returned an empty response")
            return _result("First page", 10, 3)

        llm_cls.return_value.generate_text_from_image.side_effect = generate_text_from_image
        converter = DocumentOCRToTextConverter(
            ocr_model="gpt-5.6-luna",
            ocr_model_provider="openai",
            allow_partial_ocr_failures=True,
        )

        result = converter.get_document_ocr("document.pdf")

        self.assertIn("First page", result["text"])
        self.assertEqual(result["ocr_failed_pages"], [2])
        self.assertIn("empty response", result["ocr_failed_pages_detail"][0]["reason"])

    @patch("polytext.converter.document_ocr_to_text.MultimodalLLM")
    @patch("fitz.open")
    def test_openai_document_ocr_raises_page_failure_by_default(self, fitz_open, llm_cls):
        fitz_open.return_value = _Pdf([_Page(b"page-one")])
        llm_cls.return_value.generate_text_from_image.side_effect = LLMGenerationError(
            "OpenAI returned an empty response"
        )
        converter = DocumentOCRToTextConverter(
            ocr_model="gpt-5.6-luna",
            ocr_model_provider="openai",
        )

        with self.assertRaisesRegex(LLMGenerationError, "empty response"):
            converter.get_document_ocr("document.pdf")


if __name__ == "__main__":
    unittest.main()
