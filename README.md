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
pip install doc_utils

# Full installation with all dependencies
pip install doc_utils[full]

# S3 support only
pip install doc_utils[s3]

Requirements

Python 3.6+
LibreOffice (for document conversion)

Usage Examples
Convert a document to PDF
pythonCopyfrom doc_utils import DocumentConverter

converter = DocumentConverter()
pdf_path = converter.convert_to_pdf("document.docx")
Extract text from a PDF
pythonCopyfrom doc_utils import TextLoader

loader = TextLoader()
text = loader.extract_text_from_file("document.pdf")
Work with S3 documents
pythonCopyimport boto3
from doc_utils import TextLoader

s3_client = boto3.client('s3')
loader = TextLoader(s3_client=s3_client, document_aws_bucket="my-bucket")

text = loader.get_document_text({
    "file_path": "path/to/document.pdf",
    "bucket": "my-bucket"
})



# Basic usage - extract text from a local PDF
loader = TextLoader()
text = loader.extract_text_from_file("document.pdf")

# Extract specific page range
text = loader.extract_text_from_file("document.pdf", page_range=(1, 5))

# Specify extraction backend
text = loader.extract_text_from_file("document.docx", backend='pypdf')