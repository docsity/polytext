import gzip
import os
import tempfile
import unittest

from polytext.loader.markdown import MarkdownLoader


class TestMarkdownLoaderGzip(unittest.TestCase):
    def test_get_text_from_markdown_reads_gzip_compressed_markdown(self):
        expected_text = "# Heading\n\nHello compressed markdown.\n"
        loader = MarkdownLoader(source="local", markdown_output=True)

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            temp_path = tmp.name

        try:
            with gzip.open(temp_path, "wb") as gz_file:
                gz_file.write(expected_text.encode("utf-8"))

            result = loader.get_text_from_markdown(temp_path)

            self.assertEqual(result["text"], expected_text)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
