# pdf.py
import os
import logging
import markdown
from weasyprint import HTML, CSS
from io import BytesIO
from weasyprint.text.fonts import FontConfiguration

logger = logging.getLogger(__name__)


def get_customized_pdf_from_markdown(input_markdown: str, output_file: str = None, use_custom_css: bool = True) -> bytes:
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

    def __init__(self, font_family: str = "Georgia, serif", title_color: str = "#1a5276", title_text_align: str = "center",
                 body_color: str = "white", text_color: str = "#333", h2_color: str = "#d35400", h3_color: str = "#2e86c1",
                 blockquote_border: str = "#3498db", table_header_bg: str = "#2e86c1", page_margin: str = "0.8in",
                 image_max_width: str = "80%", add_page_numbers: bool = True, font_path: str = None) -> None:
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
        self.title_text_align = title_text_align
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

    def generate_custom_css(self) -> str:
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
            margin-top: 50px;
            margin-bottom: 40px;

            @bottom-center {{
                content: counter(page);
                font-size: 16px;
                color: #000;
                margin-bottom: 30px;
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
            line-height: 1.5;
        }}

        h1 {{
            color: {self.title_color};
            font-size: 28px;
            text-align: {self.title_text_align};
            margin-bottom: 45px;
            line-height: 1.4;
        }}

        h2 {{
            color: {self.h2_color};
            font-size: 25px;
            margin-top: 10px;
            margin-bottom: 20px;
        }}

        h3 {{
            color: {self.h3_color};
            font-size: 21px;
            margin-top: 25px;
            line-height: 1.2;
            text-align: left
        }}

        p {{
            font-size: 16px;
            margin: 20px 0;
        }}
        
        /* Bullet Lists */
        ul {{
            margin-top: 30px; /* Space before the paragraph */
            margin-bottom: 25px;
            padding-left: 1em;
        }}
        
        ul li::marker {{
            font-size: 1.5em; /* Increase bullet size */
            color: #000; /* Ensuring high contrast */
        }}
        
        ul li {{
            list-style-type: disc; /* Standard bullet point */
            margin-left: 1em;
            line-height: 0.2;
        }}
        
        a {{
            color: #0066cc;
            text-decoration: underline;
        }}
        a:hover {{
            text-decoration: underline;
        }}

        blockquote {{
            border-left: 4px solid {self.blockquote_border};
            padding-left: 10px;
            font-style: italic;
            color: #000;
            margin: 15px 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        th, td {{
            border: 1px solid #000;
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

    def get_customized_pdf_from_markdown(self, input_markdown: str, output_file: str = None, use_custom_css: bool = True) -> bytes:
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
            html_content = markdown.markdown(input_markdown, extensions=['extra', 'codehilite', 'toc', 'sane_lists'])

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
