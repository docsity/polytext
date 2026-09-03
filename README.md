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
| **Python**  | Supported on **3.11 – 3.13**<br> WeasyPrint still requires its native libraries | `brew install python@3.11` | `sudo apt install python3.11` |
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

Features that require an LLM API key include:
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

### Direct OpenAI text and image processing

Text transformations, image OCR, and forced OCR of scanned documents can use
OpenAI directly. When `provider="openai"`, the default model is
`gpt-5.6-luna`.

Set `OPENAI_API_KEY` in the environment:

```bash
export OPENAI_API_KEY="your_openai_api_key"
```

Then select the provider on `BaseLoader`:

```python
from polytext.loader.base import BaseLoader

loader = BaseLoader(
    provider="openai",
    source="local",
    markdown_output=True,
)

# Text and single-image OCR
text_result = loader.get_text(input_list=["/path/to/notes.txt"])
image_result = loader.get_text(input_list=["/path/to/scan.jpg"])

# Multipage/scanned document OCR
document_loader = BaseLoader(
    provider="openai",
    source="local",
    force_ocr=True,
)
document_result = document_loader.get_text(input_list=["/path/to/scan.pdf"])
```

You may pass `llm_api_key="..."` to `BaseLoader` as an explicit credential
override. If omitted, the OpenAI SDK uses `OPENAI_API_KEY`. A custom compatible
model can be selected with `ocr_model="..."`.

Direct OpenAI processing currently covers text and images. Audio, video, and
YouTube processing continue to use the existing Gemini pipelines.

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

### S3 authentication

By default, Polytext uses the standard boto3 credential chain when loading `s3://` inputs
(environment variables, AWS profiles, IAM roles, and other boto3-supported providers).

For runtimes that need to assume an AWS role through Google OIDC, STS web identity
authentication can be enabled explicitly:

```python
from polytext.loader.base import BaseLoader

loader = BaseLoader(
    aws_auth_mode="sts_web_identity",
    aws_role_arn="arn:aws:iam::111122223333:role/ExampleRole",
    aws_region="eu-central-1",
    aws_role_session_name="polytext-session",
    gcp_id_token_audience="example-gcp-audience",
)
```

The same configuration can also come from environment variables:

```bash
POLYTEXT_AWS_AUTH_MODE=sts_web_identity
AWS_ROLE_ARN=arn:aws:iam::111122223333:role/ExampleRole
AWS_REGION=eu-central-1
AWS_ROLE_SESSION_NAME=polytext-session
GCP_ID_TOKEN_AUDIENCE=example-gcp-audience
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service_account.json
```

Polytext uses the temporary STS credentials only to create the S3 client. It does not
export them to `os.environ` and does not reset boto3's global session.

## License

MIT Licence
