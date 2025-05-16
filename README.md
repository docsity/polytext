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
# Library only – assumes system requirements are already present
pip install polytext
```

> **Heads-up:** Polytext’s PDF generator relies on [WeasyPrint] under the hood.  
> The PyPI wheel contains *only* Python code; you still need WeasyPrint’s **native libraries** (Pango, Cairo, GDK-PixBuf, HarfBuzz, Fontconfig) installed at the OS level.

### System requirements

| Requirement | Notes                                                                           | macOS (Homebrew) | Ubuntu / Debian |
|-------------|---------------------------------------------------------------------------------|------------------|-----------------|
| **Python**  | ✔️ Tested on **3.12**<br> Older versions may fail to locate WeasyPrint’s dylibs | `brew install python@3.12` | `sudo apt install python3.12` |
| **WeasyPrint – native stack** | installs Pango, Cairo, etc.                                                     | `brew install weasyprint` | `sudo apt install weasyprint` |
| **LibreOffice** | used for Office → PDF conversion                                                | `brew install --cask libreoffice` | `sudo apt install libreoffice` |


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
