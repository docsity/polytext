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
            total_token_count=5,
        ),
    )


class _FakeModels:
    def __init__(self, response):
        self.response = response
        self.generate_content_config = None
        self.generate_content_model = None

    def generate_content(self, model, contents, config):
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
    @patch("polytext.loader.youtube_llm.genai.Client")
    def test_invalid_argument_final_fallback_uses_original_temperature(self, mock_client_cls):
        clients = [
            _FakeClient(_invalid_argument_error()),
            _FakeClient(_invalid_argument_error()),
            _FakeClient(_make_response(_long_transcript())),
        ]
        mock_client_cls.side_effect = clients

        loader = YoutubeTranscriptLoaderWithLlm()
        result = loader.get_text_from_youtube("https://www.youtube.com/watch?v=example")

        self.assertEqual(result["completion_model"], "models/gemini-2.5-flash")
        self.assertEqual(clients[2].models.generate_content_config.temperature, 0.0)
        self.assertEqual(
            clients[2].models.generate_content_config.media_resolution,
            types.MediaResolution.MEDIA_RESOLUTION_LOW,
        )

    @patch("polytext.loader.youtube_llm.genai.Client")
    def test_invalid_argument_after_fallbacks_raises_empty_document_code_995(self, mock_client_cls):
        clients = [
            _FakeClient(_invalid_argument_error()),
            _FakeClient(_invalid_argument_error()),
            _FakeClient(_invalid_argument_error()),
        ]
        mock_client_cls.side_effect = clients

        loader = YoutubeTranscriptLoaderWithLlm()

        with self.assertRaises(EmptyDocument) as error_context:
            loader.get_text_from_youtube("https://www.youtube.com/watch?v=example")

        self.assertEqual(error_context.exception.code, 995)
        self.assertIn("INVALID_ARGUMENT", error_context.exception.message)


if __name__ == "__main__":
    unittest.main()
