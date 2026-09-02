import unittest
from types import SimpleNamespace
from unittest.mock import patch

from google.genai import errors as genai_errors
from google.genai import types

from polytext.loader.youtube_llm import YoutubeTranscriptLoaderWithLlm
from polytext.exceptions import EmptyDocument


def _make_response(text="full transcript"):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason="STOP")],
        usage_metadata=SimpleNamespace(
            candidates_token_count=3,
            prompt_token_count=2,
            thoughts_token_count=7,
            total_token_count=12,
        ),
    )


class _FakeModels:
    def __init__(self, response):
        self.response = response
        self.generate_content_config = None
        self.generate_content_model = None
        self.generate_content_calls = 0

    def generate_content(self, model, contents, config):
        self.generate_content_calls += 1
        self.generate_content_model = model
        self.generate_content_config = config
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class _FakeClient:
    def __init__(self, response):
        self.models = _FakeModels(response)


def _invalid_argument_error():
    return genai_errors.ClientError(
        400,
        {
            "error": {
                "code": 400,
                "message": "Request contains an invalid argument.",
                "status": "INVALID_ARGUMENT",
            }
        },
        None,
    )


def _long_transcript():
    return " ".join(
        f"This is transcript sentence number {index} with unique content."
        for index in range(20)
    )


class TestYoutubeLlmFallbacks(unittest.TestCase):
    @patch("polytext.loader.youtube_llm.logger.info")
    @patch("polytext.loader.youtube_llm.genai.Client")
    def test_logs_thinking_and_total_tokens(self, mock_client_cls, mock_info):
        mock_client_cls.return_value = _FakeClient(_make_response(_long_transcript()))

        YoutubeTranscriptLoaderWithLlm().get_text_from_youtube(
            "https://www.youtube.com/watch?v=example"
        )

        mock_info.assert_any_call("Token in thinking: %s", 7)
        mock_info.assert_any_call("Token total: %s", 12)

    def test_default_model_and_config_target_gemini_3_5_flash_lite(self):
        loader = YoutubeTranscriptLoaderWithLlm()
        config = loader.build_config(500, "transcribe")

        self.assertEqual(loader.model, "models/gemini-3.5-flash-lite")
        self.assertEqual(loader.fallback_model, "models/gemini-3.6-flash")
        self.assertEqual(loader.final_fallback_model, "models/gemini-3.7-flash")
        self.assertEqual(config.thinking_config.thinking_level.value, "MINIMAL")
        self.assertIsNone(config.thinking_config.thinking_budget)

    def test_config_adapts_to_newer_flash_models(self):
        flash_36_config = YoutubeTranscriptLoaderWithLlm(
            model="models/gemini-3.6-flash"
        ).build_config(500, "transcribe", temperature=1.0)
        flash_37_config = YoutubeTranscriptLoaderWithLlm(
            model="models/gemini-3.7-flash"
        ).build_config(500, "transcribe", temperature=1.0)

        self.assertEqual(flash_36_config.thinking_config.thinking_level.value, "MINIMAL")
        self.assertIsNone(flash_36_config.temperature)
        self.assertEqual(flash_37_config.thinking_config.thinking_level.value, "LOW")
        self.assertIsNone(flash_37_config.temperature)

    @patch("polytext.loader.youtube_llm.genai.Client")
    def test_invalid_argument_tries_each_fallback_model_once(self, mock_client_cls):
        clients = [
            _FakeClient(_invalid_argument_error()),
            _FakeClient(_make_response(_long_transcript())),
        ]
        mock_client_cls.side_effect = clients

        loader = YoutubeTranscriptLoaderWithLlm()
        result = loader.get_text_from_youtube("https://www.youtube.com/watch?v=example")

        self.assertEqual(result["completion_model"], "models/gemini-3.6-flash")
        self.assertEqual([client.models.generate_content_calls for client in clients], [1, 1])
        self.assertEqual(mock_client_cls.call_count, 2)

    @patch("polytext.loader.youtube_llm.genai.Client")
    def test_invalid_argument_uses_gemini_3_7_as_final_fallback(self, mock_client_cls):
        clients = [
            _FakeClient(_invalid_argument_error()),
            _FakeClient(_invalid_argument_error()),
            _FakeClient(_make_response(_long_transcript())),
        ]
        mock_client_cls.side_effect = clients

        result = YoutubeTranscriptLoaderWithLlm().get_text_from_youtube(
            "https://www.youtube.com/watch?v=example"
        )

        self.assertEqual(result["completion_model"], "models/gemini-3.7-flash")
        self.assertEqual([client.models.generate_content_calls for client in clients], [1, 1, 1])
        self.assertEqual(clients[1].models.generate_content_config.thinking_config.thinking_level.value, "MINIMAL")
        self.assertEqual(clients[2].models.generate_content_config.thinking_config.thinking_level.value, "LOW")

    @patch("polytext.loader.youtube_llm.genai.Client")
    def test_invalid_argument_after_all_fallbacks_raises_empty_document_995(self, mock_client_cls):
        clients = [
            _FakeClient(_invalid_argument_error()),
            _FakeClient(_invalid_argument_error()),
            _FakeClient(_invalid_argument_error()),
        ]
        mock_client_cls.side_effect = clients

        with self.assertRaises(EmptyDocument) as error_context:
            YoutubeTranscriptLoaderWithLlm().get_text_from_youtube(
                "https://www.youtube.com/watch?v=example"
            )

        self.assertEqual(error_context.exception.code, 995)
        self.assertEqual([client.models.generate_content_calls for client in clients], [1, 1, 1])


if __name__ == "__main__":
    unittest.main()
