import argparse
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


INLINE_LATEX_RE = re.compile(r"\$(?!\$)(.+?)(?<!\$)\$")
BLOCK_LATEX_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
LATEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+")
SUBSUP_RE = re.compile(r"[_^]\{?[\w+\-]+\}?")
CHEM_TOKEN_RE = re.compile(r"\b(?:[A-Z][a-z]?\d*){2,}\b")
MATH_SYMBOL_RE = re.compile(r"[=+\-*/^_∫∑√∞≈≠≤≥→←∆]")
FORMULA_LINE_RE = re.compile(r"^\s*(?:\$\$.*\$\$|.*[=^_∫∑√∞≈≠≤≥].*)\s*$")


def extract_with_pymupdf4llm(input_path: str) -> str:
    import fitz
    from pymupdf4llm import to_markdown

    document = fitz.open(input_path)
    try:
        return to_markdown(document)
    finally:
        document.close()


def extract_with_marker(input_path: str) -> str:
    try:
        # Latest API (marker>=1.0.0)
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        converter = PdfConverter(artifact_dict=create_model_dict())
        rendered = converter(input_path)
        return rendered.markdown
    except ImportError:
        # Older API (marker<1.0.0)
        from marker.convert import convert_single_pdf
        from marker.models import load_all_models
        model_lst = load_all_models()
        full_text, images, out_meta = convert_single_pdf(input_path, model_lst)
        return full_text



def save_output(text: str, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare marker and PyMuPDF4LLM on a document.")
    parser.add_argument("input", help="Local PDF path to analyze")
    parser.add_argument(
        "--mode",
        choices=["pymupdf4llm", "marker", "compare"],
        default="compare",
        help="Run only one extractor or both.",
    )
    parser.add_argument(
        "--output-prefix",
        default="tests/output/document_formula_test",
        help="Prefix used to save extractor outputs and comparison report.",
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    uid = uuid.uuid4().hex[:8]
    results: list[tuple[str, str, str | None]] = []

    if args.mode in ("pymupdf4llm", "compare"):
        text = extract_with_pymupdf4llm(input_path)
        output_path = f"{args.output_prefix}.{uid}.pymupdf4llm.md"
        save_output(text, output_path)
        results.append(("pymupdf4llm", text, output_path))
        print(f"Saved pymupdf4llm output to {output_path}")

    if args.mode in ("marker", "compare"):
        text = extract_with_marker(input_path)
        output_path = f"{args.output_prefix}.{uid}.marker.md"
        save_output(text, output_path)
        results.append(("marker", text, output_path))
        print(f"Saved marker output to {output_path}")


if __name__ == "__main__":
    main()
