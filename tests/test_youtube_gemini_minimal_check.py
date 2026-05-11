import os
import unittest

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types


load_dotenv(".env")


DEFAULT_YOUTUBE_URL = "https://www.youtube.com/watch?v=FvfsFk2p1J0"
DEFAULT_MODEL = "models/gemini-3.1-flash-lite-preview"
REFERENCE_YOUTUBE_URL = "https://www.youtube.com/watch?v=9hE5-98ZeCg"
REFERENCE_MODEL = "models/gemini-2.5-flash"
FALLBACK_MODEL = "models/gemini-3-flash-preview"
MEDIA_RESOLUTIONS = {
    "low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
    "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
    "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
}
MINIMAL_TRANSCRIPTION_PROMPT = (
    "Transcribe the spoken human speech in this YouTube video. "
    "Return only the transcript text, or exactly 'no human speech detected'."
)


@unittest.skipUnless(os.getenv("GOOGLE_API_KEY"), "GOOGLE_API_KEY is required")
class TestYoutubeGeminiMinimalCheck(unittest.TestCase):
    def get_media_resolution(self):
        value = os.getenv("YOUTUBE_MINIMAL_CHECK_MEDIA_RESOLUTION")
        if not value:
            return None

        try:
            return MEDIA_RESOLUTIONS[value.lower()]
        except KeyError:
            allowed_values = ", ".join(sorted(MEDIA_RESOLUTIONS))
            raise ValueError(
                "YOUTUBE_MINIMAL_CHECK_MEDIA_RESOLUTION must be one of: "
                f"{allowed_values}"
            )

    def generate_minimal_youtube_response(self, client, model, video_url):
        media_resolution = self.get_media_resolution()
        config = (
            types.GenerateContentConfig(media_resolution=media_resolution)
            if media_resolution is not None
            else None
        )
        return client.models.generate_content(
            model=model,
            contents=types.Content(
                parts=[
                    types.Part(file_data=types.FileData(file_uri=video_url)),
                    types.Part(text=MINIMAL_TRANSCRIPTION_PROMPT),
                ]
            ),
            config=config,
        )

    def assert_minimal_request_is_accepted(self, client, model, video_url):
        try:
            response = self.generate_minimal_youtube_response(
                client=client,
                model=model,
                video_url=video_url,
            )
        except errors.ClientError as exc:
            self.fail(
                "Minimal Gemini YouTube URL request failed with a client error. "
                f"model={model!r}, video_url={video_url!r}, "
                f"media_resolution={os.getenv('YOUTUBE_MINIMAL_CHECK_MEDIA_RESOLUTION')!r}, "
                f"details={exc.details!r}"
            )

        self.assertIsNotNone(response)
        self.assertIsInstance(response.text, str)

    def test_minimal_youtube_url_request_is_accepted_by_gemini(self):
        video_url = os.getenv("YOUTUBE_MINIMAL_CHECK_URL", DEFAULT_YOUTUBE_URL)
        model = os.getenv("YOUTUBE_MINIMAL_CHECK_MODEL", DEFAULT_MODEL)

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        self.assert_minimal_request_is_accepted(
            client=client,
            model=model,
            video_url=video_url,
        )

    def test_reference_youtube_url_request_is_accepted_by_gemini_2_5_flash(self):
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        self.assert_minimal_request_is_accepted(
            client=client,
            model=REFERENCE_MODEL,
            video_url=REFERENCE_YOUTUBE_URL,
        )

    @unittest.skipUnless(
        os.getenv("YOUTUBE_MINIMAL_CHECK_MATRIX") == "1",
        "Set YOUTUBE_MINIMAL_CHECK_MATRIX=1 to run the full live diagnostic matrix",
    )
    def test_minimal_youtube_url_diagnostic_matrix(self):
        video_url = os.getenv("YOUTUBE_MINIMAL_CHECK_URL", DEFAULT_YOUTUBE_URL)
        model = os.getenv("YOUTUBE_MINIMAL_CHECK_MODEL", DEFAULT_MODEL)
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

        cases = [
            ("reference video + reference model", REFERENCE_MODEL, REFERENCE_YOUTUBE_URL),
            ("target video + reference model", REFERENCE_MODEL, video_url),
            ("reference video + target model", model, REFERENCE_YOUTUBE_URL),
            ("target video + target model", model, video_url),
        ]

        for label, case_model, case_video_url in cases:
            with self.subTest(label=label, model=case_model, video_url=case_video_url):
                self.assert_minimal_request_is_accepted(
                    client=client,
                    model=case_model,
                    video_url=case_video_url,
                )

    @unittest.skipUnless(
        os.getenv("YOUTUBE_MINIMAL_CHECK_MATRIX") == "1",
        "Set YOUTUBE_MINIMAL_CHECK_MATRIX=1 to print manual diagnostic commands",
    )
    def test_print_manual_diagnostic_commands(self):
        video_url = os.getenv("YOUTUBE_MINIMAL_CHECK_URL", DEFAULT_YOUTUBE_URL)
        model = os.getenv("YOUTUBE_MINIMAL_CHECK_MODEL", DEFAULT_MODEL)

        commands = [
            (
                "reference video + reference model",
                f"YOUTUBE_MINIMAL_CHECK_URL={REFERENCE_YOUTUBE_URL} "
                f"YOUTUBE_MINIMAL_CHECK_MODEL={REFERENCE_MODEL} "
                "YOUTUBE_MINIMAL_CHECK_MEDIA_RESOLUTION=low "
                "python tests/test_youtube_gemini_minimal_check.py",
            ),
            (
                "target video + reference model",
                f"YOUTUBE_MINIMAL_CHECK_URL={video_url} "
                f"YOUTUBE_MINIMAL_CHECK_MODEL={REFERENCE_MODEL} "
                "YOUTUBE_MINIMAL_CHECK_MEDIA_RESOLUTION=low "
                "python tests/test_youtube_gemini_minimal_check.py",
            ),
            (
                "reference video + target model",
                f"YOUTUBE_MINIMAL_CHECK_URL={REFERENCE_YOUTUBE_URL} "
                f"YOUTUBE_MINIMAL_CHECK_MODEL={model} "
                "YOUTUBE_MINIMAL_CHECK_MEDIA_RESOLUTION=low "
                "python tests/test_youtube_gemini_minimal_check.py",
            ),
            (
                "target video + target model",
                f"YOUTUBE_MINIMAL_CHECK_URL={video_url} "
                f"YOUTUBE_MINIMAL_CHECK_MODEL={model} "
                "YOUTUBE_MINIMAL_CHECK_MEDIA_RESOLUTION=low "
                "python tests/test_youtube_gemini_minimal_check.py",
            ),
            (
                "target video + fallback model",
                f"YOUTUBE_MINIMAL_CHECK_URL={video_url} "
                f"YOUTUBE_MINIMAL_CHECK_MODEL={FALLBACK_MODEL} "
                "YOUTUBE_MINIMAL_CHECK_MEDIA_RESOLUTION=low "
                "python tests/test_youtube_gemini_minimal_check.py",
            ),
        ]

        print("\nManual diagnostic commands:")
        for label, command in commands:
            print(f"- {label}: {command}")


if __name__ == "__main__":
    unittest.main()
