import argparse
import os
import re
import sys
import uuid

import html2text
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from polytext.converter.text_to_md import text_to_md
from polytext.prompts.text_to_md import TEXT_TO_MARKDOWN_FORMULA_PROMPT


INLINE_LATEX_RE = re.compile(r"\$(?!\$)(.+?)(?<!\$)\$")
BLOCK_LATEX_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
LATEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+")
SUBSUP_RE = re.compile(r"[_^]\{?[\w+\-]+\}?")
CHEM_TOKEN_RE = re.compile(r"\b(?:[A-Z][a-z]?\d*){2,}\b")
MATH_SYMBOL_RE = re.compile(r"[=+\-*/^_∫∑√∞≈≠≤≥→←∆]")
FORMULA_LINE_RE = re.compile(r"^\s*(?:\$\$.*\$\$|.*[=^_∫∑√∞≈≠≤≥].*)\s*$")


def load_html(input_value: str) -> str:
    if input_value.startswith(("http://", "https://", "www.")):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        }
        response = requests.get(input_value, headers=headers, timeout=20)
        if response.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {response.status_code} while fetching {input_value}",
                response=response,
            )
        response.raise_for_status()
        return response.text
    with open(input_value, "r", encoding="utf-8") as handle:
        return handle.read()


def extract_direct_html2text(html_content: str) -> str:
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    return converter.handle(html_content)


def extract_with_pymupdf4llm(html_content: str) -> str:
    import fitz
    from pymupdf4llm import to_markdown

    document = fitz.open(stream=html_content.encode("utf-8"), filetype="html")
    try:
        return to_markdown(document)
    finally:
        document.close()


# def extract_with_llm(html_content: str, formula_prompt: bool, markdown_output: bool) -> str:
#     base_markdown = extract_direct_html2text(html_content)
#     prompt_template_override = TEXT_TO_MARKDOWN_FORMULA_PROMPT if formula_prompt else None
#     result = text_to_md(
#         transcript_text=base_markdown,
#         markdown_output=markdown_output,
#         llm_api_key=os.getenv("GEMINI_API_KEY"),
#         save_transcript_chunks=False,
#         prompt_template_override=prompt_template_override,
#     )
#     return result["text"]


def save_output(text: str, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare HTML extraction strategies for formulas.")
    parser.add_argument("input", help="HTML URL or local HTML file path")
    parser.add_argument(
        "--mode",
        choices=["direct", "pymupdf4llm", "llm", "compare"],
        default="compare",
        help="Run one strategy or all of them.",
    )
    parser.add_argument(
        "--formula-prompt",
        action="store_true",
        help="Use the dedicated formula-aware prompt for the LLM path.",
    )
    parser.add_argument(
        "--plain-text-output",
        action="store_true",
        help="Convert the LLM result to plain text instead of Markdown.",
    )
    parser.add_argument(
        "--output-prefix",
        default="tests/output/html_formula_test",
        help="Prefix used to save outputs and comparison report.",
    )
    args = parser.parse_args()

    uid = uuid.uuid4().hex[:8]
    markdown_output = not args.plain_text_output
    html_content = load_html(args.input)
    results: list[tuple[str, str, str]] = []

    if args.mode in ("direct", "compare"):
        text = extract_direct_html2text(html_content)
        output_path = f"{args.output_prefix}.{uid}.direct.md" if markdown_output else f"{args.output_prefix}.{uid}.direct.txt"
        save_output(text, output_path)
        results.append(("direct", text, output_path))
        print(f"Saved direct output to {output_path}")

    if args.mode in ("pymupdf4llm", "compare"):
        text = extract_with_pymupdf4llm(html_content)
        output_path = f"{args.output_prefix}.{uid}.pymupdf4llm.md" if markdown_output else f"{args.output_prefix}.{uid}.pymupdf4llm.txt"
        save_output(text, output_path)
        results.append(("pymupdf4llm", text, output_path))
        print(f"Saved pymupdf4llm output to {output_path}")

    # if args.mode in ("llm", "compare"):
    #     text = extract_with_llm(html_content, formula_prompt=args.formula_prompt, markdown_output=markdown_output)
    #     label = "llm_formula" if args.formula_prompt else "llm"
    #     output_path = f"{args.output_prefix}.{uid}.{label}.md" if markdown_output else f"{args.output_prefix}.{uid}.{label}.txt"
    #     save_output(text, output_path)
    #     results.append((label, text, output_path))
    #     print(f"Saved {label} output to {output_path}")


if __name__ == "__main__":
    main()
