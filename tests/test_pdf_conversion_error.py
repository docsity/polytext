import subprocess
import tempfile
import unittest
from unittest.mock import patch

from polytext.converter.pdf import DocumentConverter
from polytext.exceptions import ConversionError


class TestPdfConversionError(unittest.TestCase):
    @patch.object(DocumentConverter, "check_libreoffice_installed", return_value=True)
    @patch("polytext.converter.pdf.subprocess.run")
    @patch("polytext.converter.pdf.subprocess.check_call")
    def test_conversion_error_includes_libreoffice_output(
        self,
        mock_check_call,
        mock_run,
        _mock_check_libreoffice,
    ):
        libreoffice_error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["libreoffice", "--convert-to", "pdf"],
            output="convert input.docx -> output.pdf",
            stderr="Unspecified Application Error",
        )
        mock_check_call.side_effect = libreoffice_error
        mock_run.side_effect = libreoffice_error

        with tempfile.NamedTemporaryFile(suffix=".docx") as input_file:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as output_file:
                with self.assertRaises(ConversionError) as error_context:
                    DocumentConverter().convert_to_pdf(
                        input_file=input_file.name,
                        original_file=input_file.name,
                        output_file=output_file.name,
                    )

        self.assertIn("Unspecified Application Error", error_context.exception.message)
        self.assertIn("convert input.docx -> output.pdf", error_context.exception.message)


if __name__ == "__main__":
    unittest.main()
