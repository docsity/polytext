import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.generator.pdf import PDFGenerator

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize PDFGenerator
    generator = PDFGenerator(font_family="'Helvetica', sans-serif")

    # Define Markdown content
    markdown_text = """# LOREM IPSUM
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt.
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt.
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt.
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt.
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec purus ac nunc ultricies tincidunt."""

    try:
        # Call get_customized_pdf_from_markdown method
        pdf_value = generator.get_customized_pdf_from_markdown(
            input_markdown=markdown_text,
            output_file="test_custom_pdf.pdf"
        )

        print(f"Successfully generated custom pdf from markdown")

    except Exception as e:
        logging.error(f"Error generating PDF: {e}")


if __name__ == "__main__":
    main()
