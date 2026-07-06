from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

CSV_SOURCE_COLUMN = "Transcript Input Source"
DEFAULT_BUCKET_PREFIX = "s3://example-bucket/"
DEFAULT_OUTPUT_DIR = Path("tests/output/s3_image_ocr_transcription")
DESC_MARKER = "[[DESC:"

REPORT_FIELDS = [
    "row_number",
    "source_path",
    "s3_uri",
    "success",
    "completion_model",
    "completion_model_provider",
    "fallback_from_model",
    "fallback_to_model",
    "fallback_reason",
    "prompt_variant",
    "fallback_from_prompt_variant",
    "fallback_to_prompt_variant",
    "has_image_description",
    "image_descriptions",
    "elapsed_seconds",
    "prompt_tokens",
    "completion_tokens",
    "text_char_count",
    "error",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def normalize_s3_uri(source_path: str, bucket_prefix: str = DEFAULT_BUCKET_PREFIX) -> str:
    clean_source = (source_path or "").strip()
    if not clean_source:
        raise ValueError("Empty Transcript Input Source")

    if clean_source.startswith("s3://"):
        return clean_source

    clean_source = clean_source.lstrip("/")
    bucket_name = bucket_prefix.removeprefix("s3://").strip("/")
    if bucket_name and clean_source.startswith(f"{bucket_name}/"):
        return f"s3://{clean_source}"

    return f"{bucket_prefix}{clean_source}"


def load_csv_items(
    csv_path: str | Path,
    source_column: str = CSV_SOURCE_COLUMN,
    bucket_prefix: str = DEFAULT_BUCKET_PREFIX,
    limit: int | None = None,
) -> list[dict]:
    items = []
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if source_column not in (reader.fieldnames or []):
            available_columns = ", ".join(reader.fieldnames or [])
            raise ValueError(f"CSV column not found: {source_column}. Available columns: {available_columns}")

        for row_number, row in enumerate(reader, start=1):
            source_path = (row.get(source_column) or "").strip()
            if not source_path:
                logger.warning("Skipping row %s because %s is empty", row_number, source_column)
                continue

            items.append(
                {
                    "row_number": row_number,
                    "source_path": source_path,
                    "s3_uri": normalize_s3_uri(source_path, bucket_prefix=bucket_prefix),
                }
            )
            if limit is not None and len(items) >= limit:
                break

    return items


def build_loader(
    markdown_output: bool,
    target_size: int,
    timeout_minutes: int | None,
    include_image_descriptions: bool | None,
):
    from polytext.loader.base import BaseLoader

    if include_image_descriptions is not None:
        os.environ["OCR_INCLUDE_IMAGE_DESCRIPTIONS"] = "true" if include_image_descriptions else "false"

    return BaseLoader(
        gcs_client=None,
        document_gcs_bucket=None,
        target_size=target_size,
        source="cloud",
        markdown_output=markdown_output,
        timeout_minutes=timeout_minutes,
    )


def first_output_item(result: dict) -> dict:
    output_list = result.get("output_list") or []
    if output_list and isinstance(output_list[0], dict):
        return output_list[0]
    return {}


def get_result_metadata(result: dict, key: str, default=""):
    return result.get(key) or first_output_item(result).get(key) or default


def extract_image_descriptions(text: str) -> list[str]:
    return re.findall(r"\[\[DESC:.*?\]\]", text or "", flags=re.DOTALL)


def run_ocr_item(item: dict, loader) -> dict:
    start = time.time()
    base_row = {
        "row_number": item["row_number"],
        "source_path": item["source_path"],
        "s3_uri": item["s3_uri"],
    }

    try:
        result = loader.get_text(input_list=[item["s3_uri"]])
        elapsed = round(time.time() - start, 3)
        text = result.get("text") or ""
        image_descriptions = extract_image_descriptions(text)

        return {
            **base_row,
            "success": True,
            "completion_model": get_result_metadata(result, "completion_model"),
            "completion_model_provider": get_result_metadata(result, "completion_model_provider"),
            "fallback_from_model": get_result_metadata(result, "fallback_from_model"),
            "fallback_to_model": get_result_metadata(result, "fallback_to_model"),
            "fallback_reason": get_result_metadata(result, "fallback_reason"),
            "prompt_variant": get_result_metadata(result, "prompt_variant"),
            "fallback_from_prompt_variant": get_result_metadata(result, "fallback_from_prompt_variant"),
            "fallback_to_prompt_variant": get_result_metadata(result, "fallback_to_prompt_variant"),
            "has_image_description": bool(image_descriptions),
            "image_descriptions": "\n".join(image_descriptions),
            "elapsed_seconds": elapsed,
            "prompt_tokens": result.get("prompt_tokens") or 0,
            "completion_tokens": result.get("completion_tokens") or 0,
            "text_char_count": len(text),
            "error": "",
        }
    except Exception as exc:
        elapsed = round(time.time() - start, 3)
        logger.exception("OCR failed for row %s: %s", item["row_number"], item["s3_uri"])
        return {
            **base_row,
            "success": False,
            "completion_model": "",
            "completion_model_provider": "",
            "fallback_from_model": "",
            "fallback_to_model": "",
            "fallback_reason": "",
            "prompt_variant": "",
            "fallback_from_prompt_variant": "",
            "fallback_to_prompt_variant": "",
            "has_image_description": False,
            "image_descriptions": "",
            "elapsed_seconds": elapsed,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "text_char_count": 0,
            "error": str(exc),
        }


def write_report(rows: list[dict], output_path: str | Path) -> Path:
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return report_path


def default_output_path(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(output_dir) / f"ocr_s3_images_{run_id}.csv"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run OCR transcription on S3 image paths listed in a CSV export."
    )
    parser.add_argument("--csv-path", required=True, help="CSV file containing Transcript Input Source.")
    parser.add_argument("--bucket-prefix", default=DEFAULT_BUCKET_PREFIX, help="S3 bucket prefix prepended to relative CSV paths.")
    parser.add_argument("--output-path", default=None, help="Report CSV path. Defaults under tests/output.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory used when --output-path is omitted.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of CSV rows to process.")
    parser.add_argument("--dry-run", action="store_true", help="Validate CSV parsing without running OCR.")
    parser.add_argument("--target-size", type=int, default=1, help="Image target size passed to BaseLoader.")
    parser.add_argument("--timeout-minutes", type=int, default=1, help="OCR timeout passed to BaseLoader.")
    parser.add_argument("--plain-text", action="store_true", help="Disable markdown output.")
    parser.add_argument(
        "--include-image-descriptions",
        action="store_true",
        help="Force OCR_INCLUDE_IMAGE_DESCRIPTIONS=true before creating the loader.",
    )
    parser.add_argument(
        "--no-include-image-descriptions",
        action="store_true",
        help="Force OCR_INCLUDE_IMAGE_DESCRIPTIONS=false before creating the loader.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv(".env")
    args = parse_args(argv)

    include_image_descriptions = None
    if args.include_image_descriptions:
        include_image_descriptions = True
    if args.no_include_image_descriptions:
        include_image_descriptions = False

    output_path = Path(args.output_path) if args.output_path else default_output_path(args.output_dir)
    items = load_csv_items(args.csv_path, bucket_prefix=args.bucket_prefix, limit=args.limit)
    if args.dry_run:
        print(f"Loaded {len(items)} CSV item(s). OCR was not executed.")
        for item in items[:5]:
            print(item["s3_uri"])
        return 0

    loader = build_loader(
        markdown_output=not args.plain_text,
        target_size=args.target_size,
        timeout_minutes=args.timeout_minutes,
        include_image_descriptions=include_image_descriptions,
    )

    rows = []
    for index, item in enumerate(items, start=1):
        logger.info("Processing %s/%s: %s", index, len(items), item["s3_uri"])
        rows.append(run_ocr_item(item, loader))
        write_report(rows, output_path)

    success_count = sum(1 for row in rows if row["success"])
    desc_count = sum(1 for row in rows if row["has_image_description"])
    logger.info(
        "Report saved to %s. Success: %s/%s. Image descriptions found: %s.",
        output_path,
        success_count,
        len(rows),
        desc_count,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
