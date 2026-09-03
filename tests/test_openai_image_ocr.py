import os
import tempfile
import unittest
from unittest.mock import patch

from polytext.converter.ocr_to_text import OCRToTextConverter, get_ocr
from polytext.llm import GenerationResult, LLMGenerationError
from polytext.loader.base import BaseLoader
from polytext.loader.ocr import OCRLoader


class TestOpenAIImageOCR(unittest.TestCase):
    def setUp(self):
        fd, self.image_path = tempfile.mkstemp(suffix=".png")
        os.write(fd, b"small-png-fixture")
        os.close(fd)

    def tearDown(self):
        if os.path.exists(self.image_path):
            os.remove(self.image_path)

    @patch("polytext.converter.ocr_to_text.MultimodalLLM")
    def test_openai_image_ocr_returns_normalized_metadata(self, llm_cls):
        llm_cls.return_value.generate_text_from_image.return_value = GenerationResult(
            text="# Visible heading\nBody",
            prompt_tokens=31,
            completion_tokens=8,
            model="gpt-5.6-luna",
            provider="openai",
            finish_reason="completed",
        )
        converter = OCRToTextConverter(
            ocr_model="gpt-5.6-luna",
            ocr_model_provider="openai",
            llm_api_key="explicit-key",
        )

        result = converter.get_ocr(self.image_path)

        self.assertEqual(result["text"], "# Visible heading\nBody")
        self.assertEqual(result["prompt_tokens"], 31)
        self.assertEqual(result["completion_tokens"], 8)
        self.assertEqual(result["completion_model"], "gpt-5.6-luna")
        self.assertEqual(result["completion_model_provider"], "openai")
        llm_cls.assert_called_once_with(
            model="gpt-5.6-luna",
            provider="openai",
            api_key="explicit-key",
            timeout_minutes=None,
        )
        call = llm_cls.return_value.generate_text_from_image.call_args.kwargs
        self.assertEqual(call["image_data"], b"small-png-fixture")
        self.assertEqual(call["mime_type"], "image/png")

    @patch("polytext.converter.ocr_to_text.MultimodalLLM")
    def test_openai_no_readable_text_marker_becomes_empty_text(self, llm_cls):
        llm_cls.return_value.generate_text_from_image.return_value = GenerationResult(
            text="No readable text present",
            prompt_tokens=10,
            completion_tokens=4,
            model="gpt-5.6-luna",
            provider="openai",
            finish_reason="completed",
        )

        result = OCRToTextConverter(
            ocr_model="gpt-5.6-luna",
            ocr_model_provider="openai",
        ).get_ocr(self.image_path)

        self.assertEqual(result["text"], "")

    @patch("polytext.converter.ocr_to_text.MultimodalLLM")
    def test_openai_failure_does_not_fall_back_to_gemini(self, llm_cls):
        llm_cls.return_value.generate_text_from_image.side_effect = LLMGenerationError(
            "OpenAI returned an empty response"
        )
        converter = OCRToTextConverter(
            ocr_model="gpt-5.6-luna",
            ocr_model_provider="openai",
        )

        with self.assertRaisesRegex(LLMGenerationError, "empty response"):
            converter.get_ocr(self.image_path)

        self.assertEqual(llm_cls.call_count, 1)

    @patch("polytext.converter.ocr_to_text.MultimodalLLM")
    def test_get_ocr_convenience_function_propagates_openai(self, llm_cls):
        llm_cls.return_value.generate_text_from_image.return_value = GenerationResult(
            text="text",
            prompt_tokens=2,
            completion_tokens=1,
            model="gpt-5.6-luna",
            provider="openai",
            finish_reason="completed",
        )

        result = get_ocr(
            self.image_path,
            ocr_model="gpt-5.6-luna",
            ocr_model_provider="openai",
        )

        self.assertEqual(result["completion_model_provider"], "openai")

    @patch("polytext.converter.ocr_to_text.MultimodalLLM")
    def test_get_ocr_defaults_to_luna_for_openai(self, llm_cls):
        llm_cls.return_value.generate_text_from_image.return_value = GenerationResult(
            text="text",
            prompt_tokens=2,
            completion_tokens=1,
            model="gpt-5.6-luna",
            provider="openai",
            finish_reason="completed",
        )

        result = get_ocr(self.image_path, ocr_model_provider="openai")

        self.assertEqual(result["completion_model"], "gpt-5.6-luna")

    def test_base_loader_configures_image_loader_for_openai(self):
        base_loader = BaseLoader(
            provider="openai",
            ocr_model="gpt-5.6-luna",
            source="local",
        )

        loader = base_loader.init_loader_class(
            input=self.image_path,
            storage_client={},
            llm_api_key=None,
        )

        self.assertIsInstance(loader, OCRLoader)
        self.assertEqual(loader.ocr_model, "gpt-5.6-luna")
        self.assertEqual(loader.ocr_model_provider, "openai")


if __name__ == "__main__":
    unittest.main()
