import argparse
import json
import logging
import os
import re
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.cloud import storage

from polytext.converter.audio_to_text import AudioToTextConverter
from polytext.converter.video_to_audio import convert_video_to_audio
from polytext.loader.downloader.downloader import Downloader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_AUDIO_FILES = [
    "/Users/marcodelgiudice/Projects/polytext/audio_8_barbero_0_5_ore.m4a",
]
DEFAULT_TRANSCRIPTION_MODELS = [
    "gemini-2.0-flash",
    "gemini-3.1-flash-lite-preview",
]
DEFAULT_QUALITY_MODEL = "gemini-3.1-pro-preview"
DEFAULT_MAX_EVAL_CHARS = 30000
DEFAULT_OUTPUT_DIR = "test_performance/audio_model_comparison"
DEFAULT_BITRATE_QUALITY = 9
REPETITION_MIN_SENTENCE_CHARS = 120
REPETITION_MIN_REPETITIONS = 3
GCS_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
COMPARISON_METRIC_KEYS = (
    "char_count",
    "word_count",
    "line_count",
    "heading_count",
    "repeated_long_sentence_groups",
    "repeated_long_sentence_occurrences",
    "max_long_sentence_repetitions",
)


def parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    if not gcs_uri.startswith("gcs://"):
        raise ValueError(f"Not a GCS URI: {gcs_uri}")

    path = gcs_uri.replace("gcs://", "", 1)
    parts = path.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid GCS URI, expected gcs://bucket/path: {gcs_uri}")
    return parts[0], parts[1]


def is_gcs_video_uri(input_path: str) -> bool:
    if not input_path.startswith("gcs://"):
        return False
    _, file_path = parse_gcs_uri(input_path)
    return Path(file_path).suffix.lower() in GCS_VIDEO_EXTENSIONS


def cleanup_temp_paths(paths: list[str]) -> None:
    for path in paths:
        if path and os.path.exists(path):
            os.remove(path)
            logger.info("Removed temporary file %s", path)


def resolve_input_to_audio(input_path: str, bitrate_quality: int = DEFAULT_BITRATE_QUALITY) -> dict:
    if is_gcs_video_uri(input_path):
        bucket, file_path = parse_gcs_uri(input_path)
        suffix = Path(file_path).suffix.lower() or ".mp4"
        fd, temp_video_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)

        gcs_client = storage.Client()
        downloader = Downloader(gcs_client=gcs_client, document_gcs_bucket=bucket)
        downloader.download_file_from_gcs(file_path=file_path, temp_file_path=temp_video_path)

        audio_path = convert_video_to_audio(video_file=temp_video_path, bitrate_quality=bitrate_quality)
        return {
            "input_path": input_path,
            "input_type": "gcs_video",
            "audio_path": audio_path,
            "cleanup_paths": [temp_video_path, audio_path],
        }

    if input_path.startswith("gcs://"):
        raise ValueError(
            f"Unsupported GCS input for this benchmark (only video files are supported): {input_path}"
        )

    return {
        "input_path": input_path,
        "input_type": "local_audio",
        "audio_path": input_path,
        "cleanup_paths": [],
    }


def input_stem(input_path: str) -> str:
    if input_path.startswith("gcs://"):
        _, file_path = parse_gcs_uri(input_path)
        return Path(file_path).stem
    return Path(input_path).stem


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
    headings = re.findall(r"(?m)^#{2,3}\s+", clean_text)
    lines = clean_text.splitlines() if clean_text else []

    metrics = {
        "char_count": len(clean_text),
        "word_count": len(words),
        "line_count": len(lines),
        "heading_count": len(headings),
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


def transcribe_with_model(
    audio_file: str,
    transcription_model: str,
    llm_api_key: str | None,
    timeout_minutes: int | None,
) -> tuple[dict, float]:
    converter = AudioToTextConverter(
        transcription_model=transcription_model,
        markdown_output=True,
        llm_api_key=llm_api_key,
        timeout_minutes=timeout_minutes,
    )
    start = time.time()
    result = converter.transcribe_full_audio(audio_path=audio_file, save_transcript_chunks=True)
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
You are evaluating two transcriptions of the same audio content.
Model A transcript is from {model_a_name}.
Model B transcript is from {model_b_name}.

Goal:
- Compare the two transcripts and highlight likely hallucinations, insertions, and deletions.
- Be conservative: if uncertain, say uncertain.
- Focus on factual consistency between A and B, missing segments, and suspicious added content.

Return ONLY valid JSON with this schema:
{{
  "summary": "short paragraph",
  "winner": "A|B|tie",
  "confidence": 0.0,
  "hallucination_risk": {{"A": "low|medium|high", "B": "low|medium|high"}},
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
    lines = ["# Audio Transcription Comparison Report", ""]
    lines.append(f"- Generated at: `{payload['generated_at']}`")
    lines.append(f"- Quality model: `{payload['quality_model']}`")
    lines.append("")

    for item in payload["items"]:
        lines.append(f"## {item['audio_file']}")
        if item.get("error"):
            lines.append(f"- Error: `{item['error']}`")
            lines.append("")
            continue

        model_a = payload["transcription_models"][0]
        model_b = payload["transcription_models"][1]
        a_metrics = item["transcriptions"][model_a]["metrics"]
        b_metrics = item["transcriptions"][model_b]["metrics"]
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
        lines.append("")

        quality = item.get("quality_comparison", {}).get("analysis", {})
        summary = quality.get("summary") if isinstance(quality, dict) else None
        if summary:
            lines.append(f"- Quality summary: {summary}")
        else:
            lines.append("- Quality summary: unavailable (see JSON report)")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def run_benchmark(
    audio_files: list[str],
    gcs_video_files: list[str],
    transcription_models: list[str],
    quality_model: str,
    max_eval_chars: int,
    output_dir: str,
    llm_api_key: str | None,
    timeout_minutes: int | None,
    bitrate_quality: int,
) -> dict:
    if len(transcription_models) != 2:
        raise ValueError("transcription_models must contain exactly 2 models")

    run_dir = ensure_output_dir(output_dir)
    logger.info("Saving outputs in %s", run_dir)
    input_files = [*audio_files, *gcs_video_files]

    payload = {
        "generated_at": datetime.now().isoformat(),
        "audio_files": audio_files,
        "gcs_video_files": gcs_video_files,
        "input_files": input_files,
        "transcription_models": transcription_models,
        "quality_model": quality_model,
        "max_eval_chars": max_eval_chars,
        "output_dir": str(run_dir),
        "items": [],
    }

    model_a, model_b = transcription_models

    for input_path in input_files:
        logger.info("Processing %s", input_path)
        item = {
            "audio_file": input_path,
            "transcriptions": {},
        }
        resolved_input = {"input_type": "unknown", "audio_path": input_path, "cleanup_paths": []}
        try:
            resolved_input = resolve_input_to_audio(input_path=input_path, bitrate_quality=bitrate_quality)
            item["input_type"] = resolved_input["input_type"]
            item["resolved_audio_path"] = resolved_input["audio_path"]

            for model_name in transcription_models:
                logger.info("Transcribing with %s", model_name)
                result_dict, elapsed = transcribe_with_model(
                    audio_file=resolved_input["audio_path"],
                    transcription_model=model_name,
                    llm_api_key=llm_api_key,
                    timeout_minutes=timeout_minutes,
                )
                transcript_text = result_dict.get("text", "")
                metrics = compute_length_metrics(transcript_text)

                audio_stem = input_stem(input_path)
                transcript_path = run_dir / f"{sanitize_for_filename(audio_stem)}.{sanitize_for_filename(model_name)}.md"
                transcript_path.write_text(transcript_text, encoding="utf-8")

                item["transcriptions"][model_name] = {
                    "elapsed_seconds": round(elapsed, 3),
                    "metrics": metrics,
                    "prompt_tokens": result_dict.get("prompt_tokens"),
                    "completion_tokens": result_dict.get("completion_tokens"),
                    "transcript_path": str(transcript_path),
                }

            item["length_comparison"] = build_length_comparison(
                item["transcriptions"][model_a]["metrics"],
                item["transcriptions"][model_b]["metrics"],
            )
            item["quality_comparison"] = compare_quality_with_gemini_pro(
                model_a_name=model_a,
                model_b_name=model_b,
                transcript_a=Path(item["transcriptions"][model_a]["transcript_path"]).read_text(encoding="utf-8"),
                transcript_b=Path(item["transcriptions"][model_b]["transcript_path"]).read_text(encoding="utf-8"),
                quality_model=quality_model,
                max_eval_chars=max_eval_chars,
                llm_api_key=llm_api_key,
            )
        except Exception as exc:
            logger.exception("Failed processing %s", input_path)
            item["error"] = str(exc)
        finally:
            cleanup_temp_paths(resolved_input.get("cleanup_paths", []))

        payload["items"].append(item)

    json_path = run_dir / "comparison_report.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = save_markdown_report(run_dir, payload)

    return {
        "json_report": str(json_path),
        "markdown_report": str(markdown_path),
        "run_dir": str(run_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare audio transcriptions between two Gemini models and evaluate quality with a third model."
    )
    parser.add_argument(
        "--audio-files",
        nargs="+",
        default=None,
        help="Local audio files to compare",
    )
    parser.add_argument(
        "--gcs-video-files",
        nargs="+",
        default=[],
        help="GCS video files (gcs://bucket/path.mp4) to convert to audio and compare",
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
        help="Optional timeout in minutes for each transcription request",
    )
    parser.add_argument(
        "--llm-api-key",
        default=None,
        help="Optional API key override. If omitted, GOOGLE_API_KEY from env is used.",
    )
    parser.add_argument(
        "--bitrate-quality",
        type=int,
        default=DEFAULT_BITRATE_QUALITY,
        help="Bitrate quality used when converting GCS video to audio (0-9, 9 is lowest quality).",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv(".env")
    args = parse_args()
    audio_files = args.audio_files
    if audio_files is None:
        audio_files = [] if args.gcs_video_files else DEFAULT_AUDIO_FILES

    outputs = run_benchmark(
        audio_files=audio_files,
        gcs_video_files=args.gcs_video_files,
        transcription_models=args.models,
        quality_model=args.quality_model,
        max_eval_chars=args.max_eval_chars,
        output_dir=args.output_dir,
        llm_api_key=args.llm_api_key,
        timeout_minutes=args.timeout_minutes,
        bitrate_quality=args.bitrate_quality,
    )
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
