# polytext

# Doc Utils

A Python package for document conversion and text extraction.

## Features

- Convert various document formats (DOCX, ODT, PPT, etc.) to PDF
- Extract text from PDF documents
- Support for both local files and S3 storage
- Multiple PDF parsing backends (PyPDF, PyMuPDF)

## Installation

```bash
# Basic installation
pip install plytext
```

## Requirements

- Python 3.6 or higher
- LibreOffice (for PDF conversion)

## Usage

Converting Documents to PDF

```python
from polytext import convert_to_pdf, ConversionError

try:
    # Convert a document to PDF
    pdf_path = convert_to_pdf('input.docx', 'output.pdf')
    print(f"PDF saved to: {pdf_path}")
except ConversionError as e:
    print(f"Conversion failed: {e}")
```

Text Extraction

```python
from polytext import extract_text_from_file

# Extract text from any supported file
text = extract_text_from_file('document.docx')
print(f"Extracted text: {text}")
```

## License

MIT Licence
