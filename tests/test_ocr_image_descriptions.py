import os
import sys
import types
import unittest
from unittest.mock import patch


markitdown_stub = types.ModuleType("markitdown")
markitdown_stub.MarkItDown = object
sys.modules.setdefault("markitdown", markitdown_stub)

html2text_stub = types.ModuleType("html2text")
html2text_stub.HTML2Text = object
sys.modules.setdefault("html2text", html2text_stub)

pymupdf4llm_stub = types.ModuleType("pymupdf4llm")
pymupdf4llm_stub.to_markdown = lambda *args, **kwargs: ""
sys.modules.setdefault("pymupdf4llm", pymupdf4llm_stub)

from polytext.prompts.ocr import (
    OCR_IMAGE_DESCRIPTION_INSTRUCTIONS,
    OCR_TO_MARKDOWN_PROMPT,
    build_ocr_prompt,
)
from polytext.loader import BaseLoader
from polytext.loader.document_ocr import DocumentOCRLoader
from polytext.loader.ocr import OCRLoader
from polytext.converter.document_ocr_to_text import DocumentOCRToTextConverter
from polytext.converter.ocr_to_text import OCRToTextConverter


class TestOCRImageDescriptions(unittest.TestCase):
    def test_build_ocr_prompt_leaves_base_prompt_unchanged_when_disabled(self):
        self.assertEqual(
            build_ocr_prompt(
                OCR_TO_MARKDOWN_PROMPT,
                include_image_descriptions=False,
            ),
            OCR_TO_MARKDOWN_PROMPT,
        )

    def test_build_ocr_prompt_appends_image_description_instructions_when_enabled(self):
        prompt = build_ocr_prompt(
            OCR_TO_MARKDOWN_PROMPT,
            include_image_descriptions=True,
        )

        self.assertTrue(prompt.startswith(OCR_TO_MARKDOWN_PROMPT.strip()))
        self.assertIn("[[DESC:", prompt)
        self.assertIn(OCR_IMAGE_DESCRIPTION_INSTRUCTIONS.strip(), prompt)

    def test_image_description_instructions_preserve_document_language(self):
        prompt = build_ocr_prompt(
            OCR_TO_MARKDOWN_PROMPT,
            include_image_descriptions=True,
        )

        self.assertIn(
            "Each image description MUST be written in the same language as the document",
            prompt,
        )

    def test_base_loader_stores_include_image_descriptions(self):
        loader = BaseLoader(source="local", include_image_descriptions=True)

        self.assertTrue(loader.include_image_descriptions)

    def test_base_loader_defaults_image_descriptions_from_env(self):
        with patch.dict(os.environ, {"OCR_INCLUDE_IMAGE_DESCRIPTIONS": "true"}):
            loader = BaseLoader(source="local")

        self.assertTrue(loader.include_image_descriptions)

    def test_base_loader_explicit_false_overrides_image_description_env(self):
        with patch.dict(os.environ, {"OCR_INCLUDE_IMAGE_DESCRIPTIONS": "true"}):
            loader = BaseLoader(
                source="local",
                include_image_descriptions=False,
            )

        self.assertFalse(loader.include_image_descriptions)

    def test_base_loader_explicit_true_overrides_image_description_env(self):
        with patch.dict(os.environ, {"OCR_INCLUDE_IMAGE_DESCRIPTIONS": "false"}):
            loader = BaseLoader(
                source="local",
                include_image_descriptions=True,
            )

        self.assertTrue(loader.include_image_descriptions)

    def test_base_loader_passes_include_image_descriptions_to_image_ocr_loader(self):
        loader = BaseLoader(source="local", include_image_descriptions=True)
        ocr_loader = loader.init_loader_class(
            input="/tmp/example.png",
            storage_client={},
            llm_api_key=None,
            source="local",
        )

        self.assertIsInstance(ocr_loader, OCRLoader)
        self.assertTrue(ocr_loader.include_image_descriptions)

    def test_base_loader_passes_include_image_descriptions_to_document_ocr_fallback_loader(self):
        loader = BaseLoader(source="local", include_image_descriptions=True)
        document_ocr_loader = loader.init_loader_class(
            input="/tmp/example.pdf",
            storage_client={},
            llm_api_key=None,
            is_document_fallback=True,
            source="local",
        )

        self.assertIsInstance(document_ocr_loader, DocumentOCRLoader)
        self.assertTrue(document_ocr_loader.include_image_descriptions)

    def test_google_ocr_converter_builds_augmented_markdown_prompt(self):
        converter = OCRToTextConverter(include_image_descriptions=True)

        prompt = converter._build_prompt_template()

        self.assertIn("[[DESC:", prompt)

    def test_google_document_ocr_converter_builds_augmented_markdown_prompt(self):
        converter = DocumentOCRToTextConverter(include_image_descriptions=True)

        prompt = converter._build_prompt_template()

        self.assertIn("[[DESC:", prompt)

    def test_google_ocr_fallback_preserves_include_image_descriptions(self):
        converter = OCRToTextConverter(include_image_descriptions=True)
        captured = {}

        def fake_get_ocr(fallback_converter, file_for_ocr, temperature=0.0):
            captured["include_image_descriptions"] = fallback_converter.include_image_descriptions
            return {"text": "ocr text"}

        with patch.object(OCRToTextConverter, "get_ocr", fake_get_ocr):
            converter.run_fallback(
                file_for_ocr="/tmp/example.png",
                reason="retry",
                fallback_model="gemini-2.0-flash",
                fallback_temperature=1.0,
                fallback_stage=1,
            )

        self.assertTrue(captured["include_image_descriptions"])

    def test_google_document_ocr_fallback_preserves_include_image_descriptions(self):
        converter = DocumentOCRToTextConverter(include_image_descriptions=True)
        captured = {}

        def fake_get_ocr(fallback_converter, file_for_ocr, temperature=0.0):
            captured["include_image_descriptions"] = fallback_converter.include_image_descriptions
            return {"text": "ocr text"}

        with patch.object(DocumentOCRToTextConverter, "get_ocr", fake_get_ocr):
            converter.run_fallback(
                file_for_ocr="/tmp/example.png",
                reason="retry",
                fallback_model="gemini-2.0-flash",
                fallback_temperature=1.0,
                fallback_stage=1,
            )

        self.assertTrue(captured["include_image_descriptions"])
