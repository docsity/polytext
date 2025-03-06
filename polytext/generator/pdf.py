# pdf.py
import os
import logging
import markdown
from weasyprint import HTML, CSS
from io import BytesIO
from weasyprint.text.fonts import FontConfiguration

logger = logging.getLogger(__name__)


def get_customized_pdf_from_markdown(input_markdown, output_file=None, use_custom_css=True):
    """
    Convenience function to convert Markdown content to a PDF with custom styling.

    Args:
        input_markdown: The Markdown content to convert.
        output_file: Optional; if provided, the PDF will be saved to this file.
        use_custom_css (bool, optional): Whether to use custom CSS for styling. Defaults to True.

    Returns:
        A byte string containing the generated PDF.
    """
    generator = PDFGenerator()
    return generator.get_customized_pdf_from_markdown(input_markdown, output_file, use_custom_css)


class PDFGenerator:
    """
    A class to generate PDFs from Markdown content with custom CSS styling.
    """

    def __init__(self, font_family="Georgia, serif", title_color="#1a5276", body_color="white", text_color="#333",
                 h2_color="#d35400", h3_color="#2e86c1", blockquote_border="#3498db", table_header_bg="#2e86c1",
                 page_margin="0.8in", image_max_width="80%", add_page_numbers=True, font_path=None):
        """
        Initialize the PDFGenerator with custom styling options.

        Args:
            font_family: Font family for the document.
            title_color: Color for the title.
            body_color: Background color for the body.
            text_color: Text color.
            h2_color: Color for H2 headers.
            h3_color: Color for H3 headers.
            blockquote_border: Border color for blockquotes.
            table_header_bg: Background color for table headers.
            page_margin: Margin for the page.
            image_max_width: Maximum width for images.
            add_page_numbers: Whether to add page numbers.
            font_path: Path to a custom font file.
        """
        self.font_family = font_family
        self.title_color = title_color
        self.body_color = body_color
        self.text_color = text_color
        self.h2_color = h2_color
        self.h3_color = h3_color
        self.blockquote_border = blockquote_border
        self.table_header_bg = table_header_bg
        self.page_margin = page_margin
        self.image_max_width = image_max_width
        self.add_page_numbers = add_page_numbers
        self.font_path = font_path

    def generate_custom_css(self):
        """
        Generate custom CSS based on the provided styling options.

        Returns:
            A string containing the custom CSS.
        """
        font_face_css = ""
        if self.font_path and os.path.exists(self.font_path):
            logger.info(f"Using custom font: {self.font_path}")
            try:
                font_face_css = f"""
                    @font-face {{
                        font-family: {self.font_family.split(",")[0]};
                        src: url('file://{self.font_path}') format('truetype');
                        font-weight: normal;
                        font-style: normal;
                    }}
                """
                logger.info("Font-face CSS created")
            except Exception as e:
                logger.error(f"Error loading font: {e}")

        page_numbers_css = f"""
        @page {{
            size: A4;
            margin: {self.page_margin};

            @bottom-center {{
                content: counter(page) "/" counter(pages);
                font-size: 12px;
                color: #555;
            }}
        }}
        """ if self.add_page_numbers else ""

        css_template = f"""
        {page_numbers_css}

        {font_face_css} /* Include font-face only if custom font is provided */

        * {{
            font-family: {self.font_family} !important;  /* Force the font family on all elements */
        }}

        body {{
            font-family: {self.font_family};
            color: {self.text_color};
            background-color: {self.body_color};
            text-align: justify;
            line-height: 1.6;
        }}

        h1 {{
            color: {self.title_color};
            font-size: 28px;
            text-align: center;
            text-transform: uppercase;
            margin-bottom: 20px;
        }}

        h2 {{
            color: {self.h2_color};
            font-size: 22px;
            text-transform: uppercase;
            margin-top: 30px;
            border-bottom: 2px solid {self.h2_color};
            padding-bottom: 5px;
        }}

        h3 {{
            color: {self.h3_color};
            font-size: 18px;
            margin-top: 20px;
        }}

        p {{
            font-size: 14px;
            margin: 10px 0;
        }}

        blockquote {{
            border-left: 4px solid {self.blockquote_border};
            padding-left: 10px;
            font-style: italic;
            color: #555;
            margin: 15px 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}

        th {{
            background-color: {self.table_header_bg};
            color: white;
        }}

        img {{
            display: block;
            margin: 20px auto;
            max-width: {self.image_max_width};
            height: auto;
            border: 2px solid #ddd;
            padding: 5px;
        }}

        footer {{
            font-size: 12px;
            text-align: center;
            margin-top: 40px;
            color: #777;
        }}
        """
        return css_template

    def get_customized_pdf_from_markdown(self, input_markdown, output_file=None, use_custom_css=True):
        """
        Convert Markdown content to a PDF with custom styling.

        Args:
            input_markdown: The Markdown content to convert.
            output_file: Optional; if provided, the PDF will be saved to this file.
            use_custom_css (bool, optional): Whether to use custom CSS for styling. Defaults to True.

        Returns:
            A byte string containing the generated PDF.

        Raises:
            Exception: If an error occurs during PDF generation.
        """
        try:
            html_content = markdown.markdown(input_markdown, extensions=['extra', 'codehilite', 'toc'])

            # Generate PDF from HTML with Custom Styles
            pdf_buffer = BytesIO()

            if use_custom_css:
                custom_css = self.generate_custom_css()
                font_config = FontConfiguration()
                html = HTML(string=html_content)
                css = CSS(string=custom_css, font_config=font_config)
                html.write_pdf(pdf_buffer, stylesheets=[css], font_config=font_config)
            else:
                html = HTML(string=html_content)
                html.write_pdf(pdf_buffer)

            pdf_value = pdf_buffer.getvalue()

            if output_file:
                with open(output_file, 'wb') as f:
                    f.write(pdf_value)
                logger.info(f"PDF saved to {output_file}")

            return pdf_value
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            raise
