import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from polytext.converter.image_preprocessing import prepare_image_for_ocr


class TestImagePreprocessing(unittest.TestCase):
    def setUp(self):
        fd, self.image_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        Image.new("RGB", (24, 16), color="white").save(self.image_path)

    def tearDown(self):
        if os.path.exists(self.image_path):
            os.remove(self.image_path)

    @patch("polytext.converter.image_preprocessing.convert_image_to_png")
    @patch("polytext.converter.image_preprocessing.os.path.getsize")
    def test_google_keeps_existing_one_mb_threshold(self, getsize, convert):
        getsize.return_value = 2 * 1024 * 1024
        convert.return_value = "/tmp/converted.png"

        prepared = prepare_image_for_ocr(
            self.image_path,
            provider="google",
            target_size_mb=1,
        )

        convert.assert_called_once_with(self.image_path, target_size_mb=1, mime_type="image/png")
        self.assertEqual(prepared.path, "/tmp/converted.png")
        self.assertTrue(prepared.is_temporary)

    @patch("polytext.converter.image_preprocessing.convert_image_to_png")
    @patch("polytext.converter.image_preprocessing.os.path.getsize")
    def test_openai_preserves_normal_resolution_even_above_gemini_target(self, getsize, convert):
        getsize.return_value = 2 * 1024 * 1024

        prepared = prepare_image_for_ocr(
            self.image_path,
            provider="openai",
            target_size_mb=1,
        )

        convert.assert_not_called()
        self.assertEqual(prepared.path, self.image_path)
        self.assertFalse(prepared.is_temporary)

    def test_openai_resizes_images_above_ten_megapixels_to_1200_pixels(self):
        fd, large_image_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        prepared = None
        try:
            Image.new("RGB", (4000, 3000), color="white").save(large_image_path)

            prepared = prepare_image_for_ocr(
                large_image_path,
                provider="openai",
                target_size_mb=1,
            )

            self.assertTrue(prepared.is_temporary)
            with Image.open(prepared.path) as image:
                self.assertEqual(image.size, (1200, 900))
        finally:
            if prepared and prepared.is_temporary and os.path.exists(prepared.path):
                os.remove(prepared.path)
            if os.path.exists(large_image_path):
                os.remove(large_image_path)

    @patch("polytext.converter.image_preprocessing.convert_image_to_png")
    @patch("polytext.converter.image_preprocessing.os.path.getsize")
    def test_openai_converts_heic_even_when_small(self, getsize, convert):
        getsize.return_value = 500_000
        convert.return_value = "/tmp/converted.png"

        prepared = prepare_image_for_ocr(
            "/tmp/photo.heic",
            provider="openai",
            target_size_mb=1,
        )

        convert.assert_called_once_with("/tmp/photo.heic", target_size_mb=20, mime_type="image/heic")
        self.assertEqual(prepared.mime_type, "image/png")

    @patch("polytext.converter.image_preprocessing.ffmpeg.input")
    def test_gif_conversion_selects_first_frame(self, ffmpeg_input):
        from polytext.converter.image_preprocessing import convert_image_to_png

        output = ffmpeg_input.return_value.output
        output.return_value.run.return_value = None

        converted = convert_image_to_png(
            self.image_path,
            target_size_mb=20,
            mime_type="image/gif",
        )

        self.assertEqual(output.call_args.kwargs["vframes"], 1)
        os.remove(converted)

    def test_heic_is_converted_to_a_readable_png(self):
        from PIL import Image
        from pillow_heif import register_heif_opener
        from polytext.converter.image_preprocessing import convert_image_to_png

        register_heif_opener()
        fd, heic_path = tempfile.mkstemp(suffix=".heic")
        os.close(fd)
        converted = None
        try:
            Image.new("RGB", (24, 16), color="white").save(heic_path, format="HEIF")
            converted = convert_image_to_png(
                heic_path,
                target_size_mb=20,
                mime_type="image/heic",
            )

            with Image.open(converted) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.size, (24, 16))
        finally:
            if converted and os.path.exists(converted):
                os.remove(converted)
            if os.path.exists(heic_path):
                os.remove(heic_path)


if __name__ == "__main__":
    unittest.main()
