import argparse
import csv
import json
import logging
import mimetypes
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from polytext.converter.document_ocr_to_text import (
    DocumentOCRToTextConverter,
    SUPPORTED_MIME_TYPES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_DOC_OCR_PATHS = [
    "/Users/andreasolfanelli/Projects/polytext/Il Product Design.pdf",
]
DEFAULT_DOCUMENT_MODELS = [
    "gemini-2.0-flash",
    "gemini-3.1-flash-lite-preview",
]
DEFAULT_QUALITY_MODEL = "gemini-3.1-pro-preview"
DEFAULT_MAX_EVAL_CHARS = 30000
DEFAULT_OUTPUT_DIR = "tests/output/document_ocr_to_text_comparison"
REPETITION_MIN_SENTENCE_CHARS = 120
REPETITION_MIN_REPETITIONS = 3
COMPARISON_METRIC_KEYS = (
    "char_count",
    "word_count",
    "line_count",
    "heading_count",
    "repeated_long_sentence_groups",
    "repeated_long_sentence_occurrences",
    "max_long_sentence_repetitions",
)


def compute_repetition_metrics(
    text: str,
    min_sentence_chars: int = REPETITION_MIN_SENTENCE_CHARS,
    min_repetitions: int = REPETITION_MIN_REPETITIONS,
) -> dict:
    clean_text = text or ""
    if not clean_text:
        return {
            "repeated_long_sentence_groups": 0,
            "repeated_long_sentence_occurrences": 0,
            "max_long_sentence_repetitions": 0,
        }

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text) if s.strip()]
    normalized = [re.sub(r"\s+", " ", sentence).strip().lower() for sentence in sentences]
    long_sentences = [sentence for sentence in normalized if len(sentence) >= min_sentence_chars]

    if not long_sentences:
        return {
            "repeated_long_sentence_groups": 0,
            "repeated_long_sentence_occurrences": 0,
            "max_long_sentence_repetitions": 0,
        }

    counts = Counter(long_sentences)
    repeated_counts = [count for count in counts.values() if count >= min_repetitions]

    if not repeated_counts:
        return {
            "repeated_long_sentence_groups": 0,
            "repeated_long_sentence_occurrences": 0,
            "max_long_sentence_repetitions": 0,
        }

    return {
        "repeated_long_sentence_groups": len(repeated_counts),
        "repeated_long_sentence_occurrences": sum(repeated_counts),
        "max_long_sentence_repetitions": max(repeated_counts),
    }


def compute_length_metrics(text: str) -> dict:
    clean_text = text or ""
    words = re.findall(r"\b\w+\b", clean_text, flags=re.UNICODE)
    headings = re.findall(r"(?m)^#{1,3}\s+", clean_text)
    lines = clean_text.splitlines() if clean_text else []

    metrics = {
        "char_count": len(clean_text),
        "word_count": len(words),
        "line_count": len(lines),
        "heading_count": len(headings),
        "unique_word_ratio": round((len(set(word.lower() for word in words)) / len(words)), 4) if words else 0.0,
    }
    metrics.update(compute_repetition_metrics(clean_text))
    return metrics


def extract_eval_snippet(text: str, max_chars: int) -> tuple[str, bool]:
    clean_text = text or ""
    snippet = clean_text[:max_chars]
    return snippet, len(clean_text) > len(snippet)


def build_length_comparison(model_a_metrics: dict, model_b_metrics: dict) -> dict:
    comparison = {}
    for key in COMPARISON_METRIC_KEYS:
        a_value = model_a_metrics.get(key, 0)
        b_value = model_b_metrics.get(key, 0)
        delta = b_value - a_value
        delta_pct = (delta / a_value * 100) if a_value else None
        comparison[key] = {
            "model_a": a_value,
            "model_b": b_value,
            "delta_model_b_minus_model_a": delta,
            "delta_pct_vs_model_a": round(delta_pct, 3) if delta_pct is not None else None,
        }
    return comparison


def sanitize_for_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")


def parse_json_or_fallback(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {"raw_text": raw_text}


def extract_with_model(
    document_file: str,
    ocr_model: str,
    llm_api_key: str | None,
    timeout_minutes: int | None,
    markdown_output: bool,
    target_size: int,
    page_range: tuple[int, int] | None,
) -> tuple[dict, float]:
    converter = DocumentOCRToTextConverter(
        ocr_model=ocr_model,
        markdown_output=markdown_output,
        llm_api_key=llm_api_key,
        timeout_minutes=timeout_minutes,
        target_size=target_size,
        page_range=page_range,
    )
    start = time.time()
    mime_type, _ = mimetypes.guess_type(document_file)
    if mime_type in SUPPORTED_MIME_TYPES:
        result = converter.get_ocr(document_file)
    else:
        result = converter.get_document_ocr(document_file)
    elapsed = time.time() - start
    return result, elapsed


def compare_quality_with_gemini_pro(
    model_a_name: str,
    model_b_name: str,
    text_a: str,
    text_b: str,
    quality_model: str,
    max_eval_chars: int,
    llm_api_key: str | None,
) -> dict:
    text_a_snippet, text_a_truncated = extract_eval_snippet(text_a, max_eval_chars)
    text_b_snippet, text_b_truncated = extract_eval_snippet(text_b, max_eval_chars)

    prompt = f"""
You are evaluating two OCR outputs extracted from the same source document.
Model A output is from {model_a_name}.
Model B output is from {model_b_name}.

Goal:
- Compare the two OCR outputs and highlight likely OCR mistakes, missing text, repeated sections, bad formatting, and hallucinated content.
- Be conservative: if uncertain, say uncertain.
- Consider readability, structural fidelity, repeated fragments, and preservation of the original content.

Return ONLY valid JSON with this schema:
{{
  "summary": "short paragraph",
  "winner": "A|B|tie",
  "confidence": 0.0,
  "hallucination_risk": {{"A": "low|medium|high", "B": "low|medium|high"}},
  "ocr_noise_risk": {{"A": "low|medium|high", "B": "low|medium|high"}},
  "insertions": [{{"model": "A|B", "evidence": "quote", "reason": "why likely insertion"}}],
  "deletions": [{{"model": "A|B", "evidence": "quote", "reason": "why likely deletion"}}],
  "notable_differences": ["item1", "item2"],
  "limitations": "state key limits from truncated context"
}}

Context limits:
- Text A chars provided: {len(text_a_snippet)} (truncated={text_a_truncated})
- Text B chars provided: {len(text_b_snippet)} (truncated={text_b_truncated})

[TEXT_A]
{text_a_snippet}

[TEXT_B]
{text_b_snippet}
"""

    client = genai.Client(api_key=llm_api_key) if llm_api_key else genai.Client()
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ],
    )

    response = client.models.generate_content(
        model=quality_model,
        contents=prompt,
        config=config,
    )

    return {
        "quality_model": quality_model,
        "max_eval_chars": max_eval_chars,
        "text_a_truncated": text_a_truncated,
        "text_b_truncated": text_b_truncated,
        "analysis": parse_json_or_fallback(response.text),
    }


def ensure_output_dir(output_dir: str) -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_markdown_report(run_dir: Path, payload: dict) -> Path:
    report_path = run_dir / "comparison_report.md"
    lines = ["# Document OCR Comparison Report", ""]
    lines.append(f"- Generated at: `{payload['generated_at']}`")
    lines.append(f"- Quality model: `{payload['quality_model']}`")
    lines.append("")

    for item in payload["items"]:
        lines.append(f"## {item['document_file']}")
        if item.get("error"):
            lines.append(f"- Error: `{item['error']}`")
            lines.append("")
            continue

        model_a = payload["ocr_models"][0]
        model_b = payload["ocr_models"][1]
        a_metrics = item["ocr_outputs"][model_a]["metrics"]
        b_metrics = item["ocr_outputs"][model_b]["metrics"]
        lines.append(f"- `{model_a}` chars/words: {a_metrics['char_count']} / {a_metrics['word_count']}")
        lines.append(f"- `{model_b}` chars/words: {b_metrics['char_count']} / {b_metrics['word_count']}")
        lines.append(
            f"- repeated long-sentence groups (>= {REPETITION_MIN_REPETITIONS}x): "
            f"{a_metrics['repeated_long_sentence_groups']} / {b_metrics['repeated_long_sentence_groups']}"
        )
        lines.append(
            f"- max long-sentence repetitions: "
            f"{a_metrics['max_long_sentence_repetitions']} / {b_metrics['max_long_sentence_repetitions']}"
        )
        quality = item.get("quality_comparison", {}).get("analysis", {})
        summary = quality.get("summary") if isinstance(quality, dict) else None
        if summary:
            lines.append(f"- Quality summary: {summary}")
        else:
            lines.append("- Quality summary: unavailable (see JSON report)")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_csv_report(run_dir: Path, payload: dict) -> Path:
    csv_path = run_dir / "comparison_report.csv"
    fieldnames = [
        "document_file",
        "model",
        "requested_model",
        "elapsed_seconds",
        "char_count",
        "word_count",
        "line_count",
        "heading_count",
        "unique_word_ratio",
        "repeated_long_sentence_groups",
        "repeated_long_sentence_occurrences",
        "max_long_sentence_repetitions",
        "prompt_tokens",
        "completion_tokens",
        "output_path",
        "baseline_model",
        "char_count_delta_vs_baseline",
        "word_count_delta_vs_baseline",
        "line_count_delta_vs_baseline",
        "heading_count_delta_vs_baseline",
        "repeated_long_sentence_groups_delta_vs_baseline",
        "repeated_long_sentence_occurrences_delta_vs_baseline",
        "max_long_sentence_repetitions_delta_vs_baseline",
        "quality_winner",
        "quality_confidence",
        "quality_summary",
        "error",
    ]

    rows = []
    for item in payload["items"]:
        if item.get("error"):
            rows.append(
                {
                    "document_file": item["document_file"],
                    "error": item["error"],
                }
            )
            continue

        baseline_model = payload["ocr_models"][0]
        baseline_metrics = item["ocr_outputs"][baseline_model]["metrics"]
        quality_analysis = item.get("quality_comparison", {}).get("analysis", {})
        for model_name in payload["ocr_models"]:
            current = item["ocr_outputs"][model_name]
            metrics = current["metrics"]
            row = {
                "document_file": item["document_file"],
                "model": current.get("completion_model", model_name),
                "requested_model": model_name,
                "elapsed_seconds": current["elapsed_seconds"],
                "char_count": metrics["char_count"],
                "word_count": metrics["word_count"],
                "line_count": metrics["line_count"],
                "heading_count": metrics["heading_count"],
                "unique_word_ratio": metrics["unique_word_ratio"],
                "repeated_long_sentence_groups": metrics["repeated_long_sentence_groups"],
                "repeated_long_sentence_occurrences": metrics["repeated_long_sentence_occurrences"],
                "max_long_sentence_repetitions": metrics["max_long_sentence_repetitions"],
                "prompt_tokens": current.get("prompt_tokens"),
                "completion_tokens": current.get("completion_tokens"),
                "output_path": current["output_path"],
                "baseline_model": baseline_model,
                "quality_winner": quality_analysis.get("winner") if isinstance(quality_analysis, dict) else None,
                "quality_confidence": quality_analysis.get("confidence") if isinstance(quality_analysis, dict) else None,
                "quality_summary": quality_analysis.get("summary") if isinstance(quality_analysis, dict) else None,
                "error": None,
            }
            for metric_key in COMPARISON_METRIC_KEYS:
                baseline_value = baseline_metrics.get(metric_key, 0)
                current_value = metrics.get(metric_key, 0)
                row[f"{metric_key}_delta_vs_baseline"] = current_value - baseline_value
            rows.append(row)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def parse_page_range(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    start_raw, end_raw = value.split(":", 1)
    return int(start_raw), int(end_raw)


def run_benchmark(
    document_files: list[str],
    ocr_models: list[str],
    quality_model: str,
    max_eval_chars: int,
    output_dir: str,
    llm_api_key: str | None,
    timeout_minutes: int | None,
    markdown_output: bool,
    target_size: int,
    page_range: tuple[int, int] | None,
) -> dict:
    if len(ocr_models) != 2:
        raise ValueError("ocr_models must contain exactly 2 models")

    run_dir = ensure_output_dir(output_dir)
    logger.info("Saving outputs in %s", run_dir)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "document_files": document_files,
        "ocr_models": ocr_models,
        "quality_model": quality_model,
        "max_eval_chars": max_eval_chars,
        "markdown_output": markdown_output,
        "target_size": target_size,
        "page_range": page_range,
        "output_dir": str(run_dir),
        "items": [],
    }

    model_a, model_b = ocr_models

    for document_file in document_files:
        logger.info("Processing %s", document_file)
        item = {
            "document_file": document_file,
            "ocr_outputs": {},
        }
        try:
            for model_name in ocr_models:
                logger.info("Extracting OCR with %s", model_name)
                result_dict, elapsed = extract_with_model(
                    document_file=document_file,
                    ocr_model=model_name,
                    llm_api_key=llm_api_key,
                    timeout_minutes=timeout_minutes,
                    markdown_output=markdown_output,
                    target_size=target_size,
                    page_range=page_range,
                )
                extracted_text = result_dict.get("text", "")
                metrics = compute_length_metrics(extracted_text)

                document_stem = Path(document_file).stem
                output_path = run_dir / f"{sanitize_for_filename(document_stem)}.{sanitize_for_filename(model_name)}.md"
                output_path.write_text(extracted_text, encoding="utf-8")

                item["ocr_outputs"][model_name] = {
                    "elapsed_seconds": round(elapsed, 3),
                    "metrics": metrics,
                    "prompt_tokens": result_dict.get("prompt_tokens"),
                    "completion_tokens": result_dict.get("completion_tokens"),
                    "completion_model": result_dict.get("completion_model"),
                    "output_path": str(output_path),
                }

            item["length_comparison"] = build_length_comparison(
                item["ocr_outputs"][model_a]["metrics"],
                item["ocr_outputs"][model_b]["metrics"],
            )
            item["quality_comparison"] = compare_quality_with_gemini_pro(
                model_a_name=model_a,
                model_b_name=model_b,
                text_a=Path(item["ocr_outputs"][model_a]["output_path"]).read_text(encoding="utf-8"),
                text_b=Path(item["ocr_outputs"][model_b]["output_path"]).read_text(encoding="utf-8"),
                quality_model=quality_model,
                max_eval_chars=max_eval_chars,
                llm_api_key=llm_api_key,
            )
        except Exception as exc:
            logger.exception("Failed processing %s", document_file)
            item["error"] = str(exc)

        payload["items"].append(item)

    json_path = run_dir / "comparison_report.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = save_markdown_report(run_dir, payload)
    csv_path = write_csv_report(run_dir, payload)

    return {
        "json_report": str(json_path),
        "markdown_report": str(markdown_path),
        "csv_report": str(csv_path),
        "run_dir": str(run_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare document OCR outputs between two Gemini models and evaluate quality with a third model."
    )
    parser.add_argument(
        "--document-files",
        nargs="+",
        default=DEFAULT_DOC_OCR_PATHS,
        help="Local document or image files to compare",
    )
    parser.add_argument(
        "--models",
        nargs=2,
        default=DEFAULT_DOCUMENT_MODELS,
        help="Exactly 2 OCR models",
    )
    parser.add_argument(
        "--quality-model",
        default=DEFAULT_QUALITY_MODEL,
        help="Model used to compare OCR quality",
    )
    parser.add_argument(
        "--max-eval-chars",
        type=int,
        default=DEFAULT_MAX_EVAL_CHARS,
        help="Maximum chars per OCR output passed to quality comparison model",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where OCR outputs and reports are stored",
    )
    parser.add_argument(
        "--timeout-minutes",
        type=int,
        default=None,
        help="Optional timeout in minutes for each OCR request",
    )
    parser.add_argument(
        "--llm-api-key",
        default=None,
        help="Optional API key override. If omitted, GOOGLE_API_KEY from env is used.",
    )
    parser.add_argument(
        "--plain-text",
        action="store_true",
        help="Use plain text prompt instead of markdown output.",
    )
    parser.add_argument(
        "--target-size",
        type=int,
        default=1,
        help="Target size in MB for intermediate image compression.",
    )
    parser.add_argument(
        "--page-range",
        default=None,
        help="Optional page range in start:end format, 1-indexed.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv(".env")
    args = parse_args()
    outputs = run_benchmark(
        document_files=args.document_files,
        ocr_models=args.models,
        quality_model=args.quality_model,
        max_eval_chars=args.max_eval_chars,
        output_dir=args.output_dir,
        llm_api_key=args.llm_api_key,
        timeout_minutes=args.timeout_minutes,
        markdown_output=not args.plain_text,
        target_size=args.target_size,
        page_range=parse_page_range(args.page_range),
    )
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
