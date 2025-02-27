# converter/pdf.py
import os
import subprocess
import logging
from ..exceptions.base import ConversionError

logger = logging.getLogger(__name__)


def convert_to_pdf(input_file, original_file, output_file=None):
    """
    Convenience function to convert a document to PDF format using LibreOffice.

    Args:
        input_file (str): Path to the input document file to be converted
        original_file (str): Path to the original file for extension checking
        output_file (str, optional): Path where the output PDF should be saved

    Returns:
        str: Path to the generated PDF file

    Raises:
        FileNotFoundError: If the input file doesn't exist
        ConversionError: If the conversion process fails
    """
    converter = DocumentConverter()
    return converter.convert_to_pdf(input_file, original_file, output_file)


class DocumentConverter:
    """
    A class for converting various document formats to PDF using LibreOffice.

    The converter supports common document formats like TXT, DOC(X), ODT, PPT(X),
    and XLS(X). It requires LibreOffice to be installed on the system.

    Attributes:
        supported_extensions (list): List of supported file extensions
    """

    def __init__(self):
        """Initialize the DocumentConverter."""
        self.supported_extensions = [
            '.txt', '.docx', '.doc', '.odt',
            '.ppt', '.pptx', '.xlsx', '.xls', '.ods'
        ]

    @staticmethod
    def check_libreoffice_installed():
        """
        Check if LibreOffice is installed and accessible in the system PATH.

        Returns:
            bool: True if LibreOffice is installed and available, False otherwise.
        """
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

    def convert_to_pdf(self, input_file, original_file, output_file=None):
        """
        Convert a document to PDF format using LibreOffice.

        This method uses LibreOffice in headless mode to convert documents. If the input
        file is already a PDF, it will be copied to the output location.

        Args:
            input_file (str): Path to the input document file to be converted
            original_file (str): Path to the original file for extension checking
            output_file (str, optional): Path where the output PDF should be saved.
                If not provided, will use input_file name with .pdf extension

        Returns:
            str: Path to the generated PDF file

        Raises:
            FileNotFoundError: If the input file doesn't exist
            ConversionError: If the conversion process fails or LibreOffice is not installed
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file '{input_file}' does not exist.")

        # Check file extension
        _, ext = os.path.splitext(original_file)
        logger.info(os.path.splitext(original_file))
        if ext.lower() not in self.supported_extensions and ext.lower() != '.pdf':
            logger.warning(f"File extension '{ext}' may not be supported.")

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


# Alternative method with direct page_range management

    # def convert_to_pdf(self, input_file, output_file=None, page_range=None):
    #     """
    #     Converts a document to PDF format using LibreOffice.
    #     """
    #     if not os.path.exists(input_file):
    #         raise FileNotFoundError(f"Input file '{input_file}' does not exist.")
    #
    #     # Check file extension
    #     _, ext = os.path.splitext(input_file)
    #     logger.info(os.path.splitext(input_file))
    #
    #     # Set default output file name if not provided
    #     if output_file is None:
    #         output_file = os.path.splitext(input_file)[0] + '.pdf'
    #
    #     output_dir = os.path.dirname(os.path.abspath(output_file))
    #     if not os.path.exists(output_dir):
    #         os.makedirs(output_dir)
    #
    #     # If the file is already a PDF, just copy it
    #     if ext.lower() == '.pdf':
    #         import shutil
    #         shutil.copy2(input_file, output_file)
    #         logger.info(f"File is already a PDF. Copied to '{output_file}'")
    #         return output_file
    #
    #     # Check if LibreOffice is installed
    #     if not self.check_libreoffice_installed():
    #         raise ConversionError(
    #             "LibreOffice is not installed or not found in PATH. "
    #             "Please install LibreOffice to convert documents to PDF."
    #         )
    #
    #     # Record existing PDFs in the output directory
    #     import glob
    #     existing_pdfs = set(glob.glob(os.path.join(output_dir, "*.pdf")))
    #
    #     # Build the LibreOffice command
    #     convert_filter = 'pdf'
    #     if page_range:
    #         convert_filter = f'pdf:writer_pdf_Export:{{"PageRange":{{"type":"string","value":"{page_range}"}}}}'
    #
    #     command = [
    #         'libreoffice',
    #         '--headless',
    #         '--nologo',
    #         '--nofirststartwizard',
    #         '--convert-to', convert_filter,
    #         '--outdir', output_dir,
    #         input_file
    #     ]
    #
    #     try:
    #         # Run the command and capture output
    #         result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    #                                 text=True, check=False)
    #
    #         # Check if command was successful
    #         if result.returncode != 0:
    #             error_msg = f"Error during conversion: {result.stderr}"
    #             logger.error(error_msg)
    #             raise ConversionError(error_msg)
    #
    #         # Log the output to help debugging
    #         logger.info(f"LibreOffice conversion output: {result.stdout}")
    #
    #         # Find newly created PDF file
    #         current_pdfs = set(glob.glob(os.path.join(output_dir, "*.pdf")))
    #         new_pdfs = current_pdfs - existing_pdfs
    #
    #         if not new_pdfs:
    #             # Try looking in /private path as well (for macOS)
    #             if output_dir.startswith('/var/'):
    #                 private_dir = '/private' + output_dir
    #                 private_pdfs = set(glob.glob(os.path.join(private_dir, "*.pdf")))
    #                 new_pdfs = private_pdfs - existing_pdfs
    #
    #         if not new_pdfs:
    #             # Last resort: find the most recently created PDF
    #             all_pdfs = glob.glob(os.path.join(output_dir, "*.pdf"))
    #             if not all_pdfs and output_dir.startswith('/var/'):
    #                 private_dir = '/private' + output_dir
    #                 all_pdfs = glob.glob(os.path.join(private_dir, "*.pdf"))
    #
    #             if all_pdfs:
    #                 converted_file = max(all_pdfs, key=os.path.getmtime)
    #                 logger.info(f"Found most recent PDF: {converted_file}")
    #             else:
    #                 raise ConversionError(f"No PDF files found in output directory after conversion.")
    #         else:
    #             converted_file = list(new_pdfs)[0]
    #             logger.info(f"Found newly created PDF: {converted_file}")
    #
    #         # Move to desired output location if needed
    #         if converted_file != output_file:
    #             import shutil
    #             shutil.copy2(converted_file, output_file)
    #             os.remove(converted_file)  # Clean up the original
    #             logger.info(f"Moved PDF to final location: {output_file}")
    #
    #         return output_file
    #
    #     except Exception as e:
    #         error_msg = f"Error during PDF conversion: {str(e)}"
    #         logger.error(error_msg)
    #         raise ConversionError(error_msg)