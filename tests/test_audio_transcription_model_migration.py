import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from google.genai import errors as genai_errors
from polytext.converter.audio_to_text import AudioToTextConverter


class _FakeFiles:
    def upload(self, file):
        return SimpleNamespace(name="uploaded-audio")

    def delete(self, name):
        return None


class _FakeModels:
    def __init__(self):
        self.count_tokens_model = None
        self.generate_content_model = None
        self.generate_content_config = None

    def count_tokens(self, model, contents):
        self.count_tokens_model = model
        return {"tokens": 123}

    def generate_content(self, model, contents, config):
        self.generate_content_model = model
        self.generate_content_config = config
        return SimpleNamespace(
            text="transcript",
            usage_metadata=SimpleNamespace(
                candidates_token_count=11,
                prompt_token_count=7,
            ),
        )


class _FakeClient:
    def __init__(self):
        self.files = _FakeFiles()
        self.models = _FakeModels()


class _FlakyServerErrorModels:
    def __init__(self):
        self.generate_content_calls = 0

    def generate_content(self, model, contents, config):
        self.generate_content_calls += 1
        if self.generate_content_calls == 1:
            raise genai_errors.ServerError(
                500,
                {"error": {"code": 500, "status": "INTERNAL"}},
                None,
            )
        return SimpleNamespace(
            text="transcript",
            usage_metadata=SimpleNamespace(
                candidates_token_count=3,
                prompt_token_count=2,
            ),
        )


class _FlakyServerErrorClient:
    def __init__(self):
        self.models = _FlakyServerErrorModels()


class TestAudioTranscriptionModelMigration(unittest.TestCase):
    def test_default_audio_transcription_model_is_gemini_3_1_flash_lite_preview(self):
        converter = AudioToTextConverter()
        self.assertEqual(converter.transcription_model, "gemini-3.1-flash-lite-preview")

    @patch("polytext.converter.audio_to_text.os.path.getsize", return_value=21 * 1024 * 1024)
    def test_count_tokens_uses_selected_transcription_model_for_large_audio(self, _mock_getsize):
        fake_client = _FakeClient()
        selected_model = "gemini-3.1-flash-lite-preview"

        with patch("polytext.converter.audio_to_text.genai.Client", return_value=fake_client):
            converter = AudioToTextConverter(transcription_model=selected_model)
            converter.transcribe_audio("dummy.mp3")

        self.assertEqual(fake_client.models.count_tokens_model, selected_model)
        self.assertEqual(fake_client.models.generate_content_config.temperature, 0)

    def test_retries_on_genai_server_error_for_audio_transcription(self):
        fake_client = _FlakyServerErrorClient()

        with patch("polytext.converter.audio_to_text.genai.Client", return_value=fake_client):
            converter = AudioToTextConverter()
            with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_audio:
                temp_audio.write(b"fake-audio")
                temp_audio.flush()
                result = converter.transcribe_audio(temp_audio.name)

        self.assertEqual(result["transcript"], "transcript")
        self.assertEqual(fake_client.models.generate_content_calls, 2)


if __name__ == "__main__":
    unittest.main()
