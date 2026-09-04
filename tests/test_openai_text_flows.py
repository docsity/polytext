import unittest
from types import SimpleNamespace
from unittest.mock import patch

from polytext.converter.beautiful_text import BeautifulTextConverter
from polytext.converter.text_to_md import TextToMdConverter
from polytext.exceptions import EmptyDocument, LoaderError
from polytext.llm.multimodal import GenerationResult, LLMGenerationError
from polytext.loader.base import BaseLoader
from polytext.loader.plain_text import PlainTextLoader
from polytext.processor.text_merger import TextMerger


def _generation(text: str, prompt_tokens: int = 11, completion_tokens: int = 7):
    return GenerationResult(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model="gpt-5.6-luna",
        provider="openai",
        finish_reason="completed",
    )


class TestOpenAITextFlows(unittest.TestCase):
    @patch("polytext.converter.text_to_md.MultimodalLLM")
    def test_text_to_markdown_uses_openai_and_reports_its_metadata(self, llm_cls):
        llm_cls.return_value.generate_text.return_value = _generation("# Clean text")
        converter = TextToMdConverter(
            model="gpt-5.6-luna",
            model_provider="openai",
            llm_api_key="explicit-key",
        )

        result = converter.convert_text_to_md("Raw text")

        self.assertEqual(result["text"], "# Clean text")
        self.assertEqual(result["completion_model"], "gpt-5.6-luna")
        self.assertEqual(result["completion_model_provider"], "openai")
        llm_cls.assert_called_once_with(
            model="gpt-5.6-luna",
            provider="openai",
            api_key="explicit-key",
            timeout_minutes=None,
        )

    @patch("polytext.converter.text_to_md.MultimodalLLM")
    def test_text_to_markdown_propagates_timeout_to_chunk_client(self, llm_cls):
        llm_cls.return_value.generate_text.return_value = _generation("# Clean text")
        converter = TextToMdConverter(
            model="gpt-5.6-luna",
            model_provider="openai",
            timeout_minutes=3,
        )

        converter.convert_text_to_md("Raw text")

        llm_cls.assert_called_once_with(
            model="gpt-5.6-luna",
            provider="openai",
            api_key=None,
            timeout_minutes=3,
        )

    @patch("polytext.processor.text_merger.MultimodalLLM")
    def test_text_merger_uses_the_selected_openai_model(self, llm_cls):
        llm_cls.return_value.generate_text.return_value = _generation("Merged boundary")
        merger = TextMerger(
            completion_model="gpt-5.6-luna",
            completion_model_provider="openai",
            llm_api_key="explicit-key",
            n_words_for_llm_merge=5,
            timeout_minutes=4,
        )

        result = merger.merge_texts_with_llm(
            "First complete sentence. Last first sentence.",
            "First second sentence. Final complete sentence.",
        )

        self.assertEqual(result["merged_text"], "Merged boundary")
        self.assertEqual(result["prompt_tokens"], 11)
        self.assertEqual(result["completion_tokens"], 7)
        llm_cls.assert_called_once_with(
            model="gpt-5.6-luna",
            provider="openai",
            api_key="explicit-key",
            timeout_minutes=4,
        )

    @patch("polytext.converter.beautiful_text.MultimodalLLM")
    def test_beautiful_text_uses_openai(self, llm_cls):
        llm_cls.return_value.generate_text.return_value = _generation("## Chapter\nClean")
        converter = BeautifulTextConverter(
            model="gpt-5.6-luna",
            model_provider="openai",
            llm_api_key="explicit-key",
        )

        result = converter.convert("Raw text", active_chapters=False)

        self.assertEqual(result["text"], "## Chapter\nClean")
        self.assertEqual(result["completion_model_provider"], "openai")
        llm_cls.assert_called_once_with(
            model="gpt-5.6-luna",
            provider="openai",
            api_key="explicit-key",
            timeout_minutes=None,
        )

    @patch("polytext.loader.plain_text.text_to_md")
    def test_plain_text_loader_propagates_openai_configuration(self, text_to_md_fn):
        def fake_text_to_md(**kwargs):
            return {
                "text": "clean",
                "completion_tokens": 1,
                "prompt_tokens": 2,
                "completion_model": kwargs["model"],
                "completion_model_provider": kwargs["model_provider"],
            }

        text_to_md_fn.side_effect = fake_text_to_md
        loader = PlainTextLoader(
            model="gpt-5.6-luna",
            model_provider="openai",
            llm_api_key="explicit-key",
            timeout_minutes=2,
        )

        result = loader.get_plain_text("Raw text")

        self.assertEqual(result["completion_model"], "gpt-5.6-luna")
        self.assertEqual(result["completion_model_provider"], "openai")
        self.assertEqual(text_to_md_fn.call_args.kwargs["timeout_minutes"], 2)

    def test_base_loader_configures_plain_text_for_openai(self):
        base_loader = BaseLoader(
            provider="openai",
            ocr_model="gpt-5.6-luna",
            llm_api_key="explicit-key",
            source="local",
        )

        loader = base_loader.init_loader_class(
            input="A" * 401,
            storage_client={},
            llm_api_key="explicit-key",
        )

        self.assertIsInstance(loader, PlainTextLoader)
        self.assertEqual(loader.model, "gpt-5.6-luna")
        self.assertEqual(loader.model_provider, "openai")

    def test_base_loader_separates_text_and_ocr_models(self):
        base_loader = BaseLoader(
            provider="openai",
            text_model="gpt-5.6-luna",
            ocr_model="gpt-5.6-terra",
            source="local",
        )

        text_loader = base_loader.init_loader_class(
            input="A" * 401,
            storage_client={},
            llm_api_key=None,
        )
        image_loader = base_loader.init_loader_class(
            input="page.png",
            storage_client={},
            llm_api_key=None,
        )

        self.assertEqual(text_loader.model, "gpt-5.6-luna")
        self.assertEqual(image_loader.ocr_model, "gpt-5.6-terra")

    def test_text_model_defaults_to_ocr_model_for_backward_compatibility(self):
        base_loader = BaseLoader(
            provider="google",
            ocr_model="custom-gemini-model",
            source="local",
        )

        text_loader = base_loader.init_loader_class(
            input="A" * 401,
            storage_client={},
            llm_api_key=None,
        )

        self.assertEqual(base_loader.text_model, "custom-gemini-model")
        self.assertEqual(text_loader.model, "custom-gemini-model")

    def test_text_model_does_not_shift_existing_positional_timeout(self):
        base_loader = BaseLoader(True, None, "google", "temp", "custom-gemini-model", 7)

        self.assertEqual(base_loader.ocr_model, "custom-gemini-model")
        self.assertEqual(base_loader.text_model, "custom-gemini-model")
        self.assertEqual(base_loader.timeout_minutes, 7)

    @patch("polytext.loader.base.BeautifulTextConverter")
    def test_base_loader_uses_text_model_for_beautiful_text(self, converter_cls):
        base_loader = BaseLoader(
            provider="openai",
            ocr_model="gpt-5.6-terra",
            text_model="gpt-5.6-luna",
            source="local",
        )
        raw_result = {
            "text": "Raw text",
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "type": "text",
        }
        converter_cls.return_value.convert.return_value = {
            "text": "# Clean",
            "completion_tokens": 1,
            "prompt_tokens": 2,
            "completion_model": "gpt-5.6-luna",
            "completion_model_provider": "openai",
            "chapters": [{"title": "Clean"}],
        }

        with patch.object(base_loader, "extract_raw_text_for_beautiful_text", return_value=raw_result):
            base_loader.get_beautiful_text(["Raw text"])

        converter_cls.assert_called_once_with(
            llm_api_key=None,
            model="gpt-5.6-luna",
            model_provider="openai",
            timeout_minutes=None,
        )

    @patch("polytext.loader.base.BeautifulTextConverter")
    def test_beautiful_text_output_error_becomes_loader_error(self, converter_cls):
        base_loader = BaseLoader(provider="openai", source="local")
        raw_result = {
            "text": "Raw text",
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "type": "text",
        }
        converter_cls.return_value.convert.side_effect = EmptyDocument(
            "OpenAI beautiful-text processing returned unusable output (content_filter)",
            code=993,
        )

        with patch.object(base_loader, "extract_raw_text_for_beautiful_text", return_value=raw_result):
            with patch("polytext.loader.base._capture_exception_for_sentry"):
                with self.assertRaises(LoaderError) as error_context:
                    base_loader.get_beautiful_text(["Raw text"])

        self.assertEqual(error_context.exception.status, 422)
        self.assertEqual(error_context.exception.code, "CONTENT_FILTER")

    @patch("polytext.converter.text_to_md.MultimodalLLM")
    def test_text_chunk_maps_openai_content_filter_to_empty_document(self, llm_cls):
        llm_cls.return_value.generate_text.side_effect = LLMGenerationError(
            "filtered",
            reason="content_filter",
        )
        converter = TextToMdConverter(
            model="gpt-5.6-luna",
            model_provider="openai",
        )

        with self.assertRaises(EmptyDocument) as error_context:
            converter.convert_text_to_md("Raw text")

        self.assertEqual(error_context.exception.code, 993)

    @patch("polytext.processor.text_merger.MultimodalLLM")
    def test_text_merge_maps_openai_token_limit_without_local_fallback(self, llm_cls):
        llm_cls.return_value.generate_text.side_effect = LLMGenerationError(
            "limited",
            reason="max_output_tokens",
        )
        merger = TextMerger(
            completion_model="gpt-5.6-luna",
            completion_model_provider="openai",
        )

        with self.assertRaises(EmptyDocument) as error_context:
            merger.merge_texts_with_llm("First text.", "Second text.")

        self.assertEqual(error_context.exception.code, 999)
        self.assertEqual(llm_cls.return_value.generate_text.call_count, 1)

    @patch("polytext.converter.beautiful_text.MultimodalLLM")
    def test_beautiful_text_maps_openai_empty_output(self, llm_cls):
        llm_cls.return_value.generate_text.side_effect = LLMGenerationError(
            "empty",
            reason="empty_response",
        )
        converter = BeautifulTextConverter(
            model="gpt-5.6-luna",
            model_provider="openai",
        )

        with self.assertRaises(EmptyDocument) as error_context:
            converter.convert("Raw text", active_chapters=False)

        self.assertEqual(error_context.exception.code, 994)

    @patch("polytext.converter.text_to_md.MultimodalLLM")
    def test_google_text_error_is_not_remapped_as_openai_error(self, llm_cls):
        original_error = LLMGenerationError(
            "Gemini output failed",
            reason="empty_response",
        )
        llm_cls.return_value.generate_text.side_effect = original_error
        converter = TextToMdConverter(
            model="gemini-3.1-flash-lite",
            model_provider="google",
        )

        with self.assertRaises(LLMGenerationError) as error_context:
            converter.convert_text_to_md("Raw text")

        self.assertIs(error_context.exception, original_error)

    @patch("polytext.converter.text_to_md.MultimodalLLM")
    def test_google_text_client_keeps_existing_timeout_behavior(self, llm_cls):
        converter = TextToMdConverter(
            model="gemini-3.1-flash-lite",
            model_provider="google",
            timeout_minutes=3,
        )

        converter.get_client()

        llm_cls.assert_called_once_with(
            model="gemini-3.1-flash-lite",
            provider="google",
            api_key=None,
            timeout_minutes=None,
        )


if __name__ == "__main__":
    unittest.main()
