# converter.py
import os
import subprocess
import logging
from .exceptions import ConversionError

logger = logging.getLogger(__name__)


class DocumentConverter:
    """Converts various document formats to PDF using LibreOffice."""

    def __init__(self):
        """Initialize the DocumentConverter."""
        self.supported_extensions = [
            '.txt', '.docx', '.doc', '.odt',
            '.ppt', '.pptx', '.xlsx', '.xls', '.ods'
        ]

    @staticmethod
    def check_libreoffice_installed():
        """Check if LibreOffice is installed and available."""
        try:
            subprocess.run(
                ['libreoffice', '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def convert_to_pdf(self, input_file, output_file=None):
        """
        Converts a document to PDF format using LibreOffice.

        Args:
            input_file: Path to the input document file
            output_file: Path to the output PDF file (optional) If not provided, the output file will have the same name as the input file with a .pdf extension.

        Returns:
            Path to the output PDF file

        Raises:
            FileNotFoundError: If input file doesn't exist
            ConversionError: If conversion fails
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file '{input_file}' does not exist.")

        # Check file extension
        _, ext = os.path.splitext(input_file)
        logger.info(os.path.splitext(input_file))
        # if ext.lower() not in self.supported_extensions and ext.lower() != '.pdf':
        #     logger.warning(f"File extension '{ext}' may not be supported.")

        # Set default output file name if not provided
        if output_file is None:
            output_file = os.path.splitext(input_file)[0] + '.pdf'

        output_dir = os.path.dirname(os.path.abspath(output_file))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # If the file is already a PDF, just copy it
        if ext.lower() == '.pdf':
            import shutil
            shutil.copy2(input_file, output_file)
            logger.info(f"File is already a PDF. Copied to '{output_file}'")
            return output_file

        # Check if LibreOffice is installed
        if not self.check_libreoffice_installed():
            raise ConversionError(
                "LibreOffice is not installed or not found in PATH. "
                "Please install LibreOffice to convert documents to PDF."
            )

        # Build the LibreOffice command
        command = [
            'libreoffice',
            '--headless',
            '--nologo',
            '--nofirststartwizard',
            '--convert-to', 'pdf',
            '--outdir', output_dir,
            input_file
        ]

        try:
            # Suppress Java runtime warnings by redirecting stderr
            subprocess.check_call(command, stderr=subprocess.DEVNULL)
            logger.info(f"Conversion successful: '{output_file}'")
        except subprocess.CalledProcessError as e:
            error_msg = f"Error during conversion: {e}"
            logger.error(error_msg)
            raise ConversionError(error_msg, e)

        # After conversion, ensure the output file is correctly named
        converted_file = os.path.join(
            output_dir,
            os.path.splitext(os.path.basename(input_file))[0] + '.pdf'
        )
        if converted_file != output_file:
            os.rename(converted_file, output_file)

        return output_file