![polytext](https://github.com/docsity/polytext/blob/main/images/logo.jpg)

# polytext
[![PyPI - Version](https://img.shields.io/pypi/v/polytext)](https://pypi.org/project/polytext/)
[![PyPI Build](https://github.com/docsity/polytext/actions/workflows/main.yml/badge.svg)](https://github.com/docsity/polytext/actions)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/polytext)](https://pypi.org/project/polytext/)
[![PyPI Downloads](https://static.pepy.tech/badge/polytext)](https://pypi.org/project/polytext/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/polytext)](https://pypi.org/project/polytext/)

# Doc Utils

A Python package for document conversion and text extraction.

## Features

- Convert various document formats (DOCX, ODT, PPT, etc.) to PDF
- Extract text from PDF, Markdown, IMAGE, and audio files
- Support for both local files and S3/GCS cloud storage
- Multiple PDF parsing backends (PyPDF, PyMuPDF)
- Transcribe audio & video files (local or cloud) to text/markdown
- Extract YouTube video transcripts
- Extract text from URLs

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

Features that require the API key for Google Gemini are:
- audio
- video
- image
- youtube

```python
from polytext.loader.base import BaseLoader

llm_api_key = "your_google_gemini_api_key"  # Set your Google Gemini API key here

# Instantiate the loader 
loader = BaseLoader(llm_api_key=llm_api_key)
```

Text or Markdown Extraction

```python
from polytext.loader.base import BaseLoader

markdown_output = False # Change if you want to extract text as markdown
source = "local" # Change to "cloud" if you want to extract from cloud storage (s3 or GCS)

# Instantiate the loader (optionally set markdown_output, llm_api_key, etc.)
loader = BaseLoader(markdown_output=markdown_output, source=source)

# Extract text from a local file
result = loader.get_text(input_list=["/path/to/document.docx"])
print(result["text"])
# Extract text from cloud file
result = loader.get_text(input_list=["s3://your-bucket/path/to/document.docx"])
print(result["text"])

# Extract text from a markdown file (local)
result = loader.get_text(input_list=["/path/to/document.md"])
print(result["text"])
# Extract text from cloud file
result = loader.get_text(input_list=["s3://your-bucket/path/to/document.md"])
print(result["text"])

# Extract text from an audio file (local)
result = loader.get_text(input_list=["/path/to/audio.mp3"])
print(result["text"])
# Extract text from cloud file
result = loader.get_text(input_list=["s3://your-bucket/path/to/audio.mp3"])
print(result["text"])

# Extract text from a video file (local)
result = loader.get_text(input_list=["/path/to/video.mp4"])
print(result["text"])
# Extract text from cloud file
result = loader.get_text(input_list=["s3://your-bucket/path/to/video.mp4"])
print(result["text"])

# Extract text from Image (local)
result = loader.get_text(input_list=["/path/to/image.jpg"])
print(result["text"])
# Extract text from cloud file
result = loader.get_text(input_list=["s3://your-bucket/path/to/image.jpg"])
print(result["text"])

# Extract transcript from a YouTube video
result = loader.get_text(input_list=["https://www.youtube.com/watch?v=xxxx"])
print(result["text"])

# Extract text from a URL
result = loader.get_text(input_list=["https://www.domain-name.com/path"])
print(result["text"])
```

## License

MIT Licence
