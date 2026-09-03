import unittest
from types import SimpleNamespace
from unittest.mock import patch

from polytext.converter.beautiful_text import BeautifulTextConverter
from polytext.converter.text_to_md import TextToMdConverter
from polytext.llm.multimodal import GenerationResult
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
        )

    @patch("polytext.processor.text_merger.MultimodalLLM")
    def test_text_merger_uses_the_selected_openai_model(self, llm_cls):
        llm_cls.return_value.generate_text.return_value = _generation("Merged boundary")
        merger = TextMerger(
            completion_model="gpt-5.6-luna",
            completion_model_provider="openai",
            llm_api_key="explicit-key",
            n_words_for_llm_merge=5,
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
        )

        result = loader.get_plain_text("Raw text")

        self.assertEqual(result["completion_model"], "gpt-5.6-luna")
        self.assertEqual(result["completion_model_provider"], "openai")

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


if __name__ == "__main__":
    unittest.main()
