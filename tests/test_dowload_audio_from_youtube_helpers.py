import unittest
from unittest.mock import patch

import yt_dlp

from tests.test_dowload_audio_from_youtube import download_youtube_m4a


class _FakeYoutubeDL:
    def __init__(self, should_fail: bool):
        self.should_fail = should_fail

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, _url, download=True):
        if self.should_fail:
            raise yt_dlp.utils.DownloadError("ERROR: The downloaded file is empty")
        return {"id": "ok", "download": download}


class TestDownloadAudioFromYoutubeHelpers(unittest.TestCase):
    @patch("tests.test_dowload_audio_from_youtube.yt_dlp.YoutubeDL")
    def test_falls_back_to_second_download_strategy(self, mock_yt_dlp_cls):
        mock_yt_dlp_cls.side_effect = [_FakeYoutubeDL(should_fail=True), _FakeYoutubeDL(should_fail=False)]

        output_path = download_youtube_m4a(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            outdir="/tmp",
            title="unit_test_audio",
        )

        self.assertEqual(output_path, "/tmp/unit_test_audio.m4a")
        self.assertEqual(mock_yt_dlp_cls.call_count, 2)

        first_opts = mock_yt_dlp_cls.call_args_list[0].args[0]
        second_opts = mock_yt_dlp_cls.call_args_list[1].args[0]
        self.assertIn("[protocol=https]", first_opts["format"])
        self.assertEqual(second_opts["format"], "bestaudio/best")


if __name__ == "__main__":
    unittest.main()
