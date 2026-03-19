import argparse
import csv
import json
import logging
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

from polytext.loader.youtube_llm import YoutubeTranscriptLoaderWithLlm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=xY5x0q5JoPI",
    "https://www.youtube.com/watch?v=w82a1FT5o88",
    "https://www.youtube.com/watch?v=V8eLdbKXGzk",
    "https://www.youtube.com/watch?v=yoD8RMq2OkU",
    "https://www.youtube.com/watch?v=Md4Fs-Zc3tg&t=173s"
]
DEFAULT_TRANSCRIPTION_MODELS = [
    "models/gemini-2.5-flash",
    "models/gemini-3.1-flash-lite-preview",
]
DEFAULT_QUALITY_MODEL = "gemini-3.1-pro-preview"
DEFAULT_MAX_EVAL_CHARS = 30000
DEFAULT_OUTPUT_DIR = "tests/output/youtube_model_comparison"
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


def fetch_with_model(
    youtube_url: str,
    transcription_model: str,
    llm_api_key: str | None,
    timeout_minutes: int | None,
    markdown_output: bool,
) -> tuple[dict, float]:
    loader = YoutubeTranscriptLoaderWithLlm(
        model=transcription_model,
        llm_api_key=llm_api_key,
        markdown_output=markdown_output,
        timeout_minutes=timeout_minutes,
    )
    start = time.time()
    result = loader.get_text_from_youtube(video_url=youtube_url)
    elapsed = time.time() - start
    return result, elapsed


def compare_quality_with_gemini_pro(
    model_a_name: str,
    model_b_name: str,
    transcript_a: str,
    transcript_b: str,
    quality_model: str,
    max_eval_chars: int,
    llm_api_key: str | None,
) -> dict:
    transcript_a_snippet, transcript_a_truncated = extract_eval_snippet(transcript_a, max_eval_chars)
    transcript_b_snippet, transcript_b_truncated = extract_eval_snippet(transcript_b, max_eval_chars)

    prompt = f"""
You are evaluating two transcriptions of the same YouTube video.
Model A transcript is from {model_a_name}.
Model B transcript is from {model_b_name}.

Goal:
- Compare the two transcripts and highlight likely hallucinations, insertions, deletions, missing sections, and repeated content.
- Be conservative: if uncertain, say uncertain.
- Consider structure, repetitions, likely omissions, suspicious added content, and overall usefulness.

Return ONLY valid JSON with this schema:
{{
  "summary": "short paragraph",
  "winner": "A|B|tie",
  "confidence": 0.0,
  "hallucination_risk": {{"A": "low|medium|high", "B": "low|medium|high"}},
  "repetition_risk": {{"A": "low|medium|high", "B": "low|medium|high"}},
  "insertions": [{{"model": "A|B", "evidence": "quote", "reason": "why likely insertion"}}],
  "deletions": [{{"model": "A|B", "evidence": "quote", "reason": "why likely deletion"}}],
  "notable_differences": ["item1", "item2"],
  "limitations": "state key limits from truncated context"
}}

Context limits:
- Transcript A chars provided: {len(transcript_a_snippet)} (truncated={transcript_a_truncated})
- Transcript B chars provided: {len(transcript_b_snippet)} (truncated={transcript_b_truncated})

[TRANSCRIPT_A]
{transcript_a_snippet}

[TRANSCRIPT_B]
{transcript_b_snippet}
"""

    if llm_api_key:
        client = genai.Client(api_key=llm_api_key)
    else:
        client = genai.Client()

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
        "transcript_a_truncated": transcript_a_truncated,
        "transcript_b_truncated": transcript_b_truncated,
        "analysis": parse_json_or_fallback(response.text),
    }


def ensure_output_dir(output_dir: str) -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_markdown_report(run_dir: Path, payload: dict) -> Path:
    report_path = run_dir / "comparison_report.md"
    lines = ["# YouTube Transcript Comparison Report", ""]
    lines.append(f"- Generated at: `{payload['generated_at']}`")
    lines.append(f"- Quality model: `{payload['quality_model']}`")
    lines.append("")

    for item in payload["items"]:
        lines.append(f"## {item['youtube_url']}")
        if item.get("error"):
            lines.append(f"- Error: `{item['error']}`")
            lines.append("")
            continue

        model_a = payload["transcription_models"][0]
        model_b = payload["transcription_models"][1]
        a_metrics = item["transcripts"][model_a]["metrics"]
        b_metrics = item["transcripts"][model_b]["metrics"]
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
        "youtube_url",
        "model",
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
        "transcript_path",
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
                    "youtube_url": item["youtube_url"],
                    "error": item["error"],
                }
            )
            continue

        baseline_model = payload["transcription_models"][0]
        baseline_metrics = item["transcripts"][baseline_model]["metrics"]
        quality_analysis = item.get("quality_comparison", {}).get("analysis", {})
        for model_name in payload["transcription_models"]:
            current = item["transcripts"][model_name]
            metrics = current["metrics"]
            row = {
                "youtube_url": item["youtube_url"],
                "model": model_name,
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
                "transcript_path": current["transcript_path"],
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


def run_benchmark(
    youtube_urls: list[str],
    transcription_models: list[str],
    quality_model: str,
    max_eval_chars: int,
    output_dir: str,
    llm_api_key: str | None,
    timeout_minutes: int | None,
    markdown_output: bool,
) -> dict:
    if len(transcription_models) != 2:
        raise ValueError("transcription_models must contain exactly 2 models")

    run_dir = ensure_output_dir(output_dir)
    logger.info("Saving outputs in %s", run_dir)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "youtube_urls": youtube_urls,
        "transcription_models": transcription_models,
        "quality_model": quality_model,
        "max_eval_chars": max_eval_chars,
        "markdown_output": markdown_output,
        "output_dir": str(run_dir),
        "items": [],
    }

    model_a, model_b = transcription_models

    for youtube_url in youtube_urls:
        logger.info("Processing %s", youtube_url)
        item = {
            "youtube_url": youtube_url,
            "transcripts": {},
        }
        try:
            for model_name in transcription_models:
                logger.info("Fetching transcript with %s", model_name)
                result_dict, elapsed = fetch_with_model(
                    youtube_url=youtube_url,
                    transcription_model=model_name,
                    llm_api_key=llm_api_key,
                    timeout_minutes=timeout_minutes,
                    markdown_output=markdown_output,
                )
                transcript_text = result_dict.get("text", "")
                metrics = compute_length_metrics(transcript_text)

                url_slug = sanitize_for_filename(youtube_url)
                transcript_path = run_dir / f"{url_slug}.{sanitize_for_filename(model_name)}.md"
                transcript_path.write_text(transcript_text, encoding="utf-8")

                item["transcripts"][model_name] = {
                    "elapsed_seconds": round(elapsed, 3),
                    "metrics": metrics,
                    "prompt_tokens": result_dict.get("prompt_tokens"),
                    "completion_tokens": result_dict.get("completion_tokens"),
                    "transcript_path": str(transcript_path),
                }

            item["length_comparison"] = build_length_comparison(
                item["transcripts"][model_a]["metrics"],
                item["transcripts"][model_b]["metrics"],
            )
            item["quality_comparison"] = compare_quality_with_gemini_pro(
                model_a_name=model_a,
                model_b_name=model_b,
                transcript_a=Path(item["transcripts"][model_a]["transcript_path"]).read_text(encoding="utf-8"),
                transcript_b=Path(item["transcripts"][model_b]["transcript_path"]).read_text(encoding="utf-8"),
                quality_model=quality_model,
                max_eval_chars=max_eval_chars,
                llm_api_key=llm_api_key,
            )
        except Exception as exc:
            logger.exception("Failed processing %s", youtube_url)
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
        description="Compare YouTube transcripts between two Gemini models and evaluate quality with a third model."
    )
    parser.add_argument(
        "--youtube-urls",
        nargs="+",
        default=DEFAULT_YOUTUBE_URLS,
        help="YouTube URLs to compare",
    )
    parser.add_argument(
        "--models",
        nargs=2,
        default=DEFAULT_TRANSCRIPTION_MODELS,
        help="Exactly 2 transcription models",
    )
    parser.add_argument(
        "--quality-model",
        default=DEFAULT_QUALITY_MODEL,
        help="Model used to compare transcript quality",
    )
    parser.add_argument(
        "--max-eval-chars",
        type=int,
        default=DEFAULT_MAX_EVAL_CHARS,
        help="Maximum chars per transcript passed to quality comparison model",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where transcripts and reports are stored",
    )
    parser.add_argument(
        "--timeout-minutes",
        type=int,
        default=None,
        help="Optional timeout in minutes for each transcript request",
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
    return parser.parse_args()


def main() -> None:
    load_dotenv(".env")
    args = parse_args()
    outputs = run_benchmark(
        youtube_urls=args.youtube_urls,
        transcription_models=args.models,
        quality_model=args.quality_model,
        max_eval_chars=args.max_eval_chars,
        output_dir=args.output_dir,
        llm_api_key=args.llm_api_key,
        timeout_minutes=args.timeout_minutes,
        markdown_output=not args.plain_text,
    )
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
