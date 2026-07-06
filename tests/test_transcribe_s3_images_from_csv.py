import csv
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from test_transcribe_s3_images_from_csv_script import (
    DESC_MARKER,
    extract_image_descriptions,
    main,
    load_csv_items,
    normalize_s3_uri,
    run_ocr_item,
    write_report,
)


class FakeLoader:
    def __init__(self, response=None, error=None):
        self.response = response or {}
        self.error = error
        self.seen_inputs = []

    def get_text(self, input_list):
        self.seen_inputs.append(input_list)
        if self.error:
            raise self.error
        return self.response


def test_normalize_s3_uri_adds_bucket_prefix():
    source = "uploads/image/2026/06/29/example.jpg"

    assert normalize_s3_uri(source) == "s3://example-bucket/uploads/image/2026/06/29/example.jpg"


def test_normalize_s3_uri_keeps_existing_s3_uri():
    source = "s3://example-bucket/uploads/image/2026/06/29/example.jpg"

    assert normalize_s3_uri(source) == source


def test_load_csv_items_reads_transcript_input_source_column(tmp_path):
    csv_path = tmp_path / "activity.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["ID", "Transcript Input Source"])
        writer.writeheader()
        writer.writerow({"ID": "42", "Transcript Input Source": "uploads/image/example.jpg"})

    items = load_csv_items(csv_path)

    assert items == [
        {
            "row_number": 1,
            "source_path": "uploads/image/example.jpg",
            "s3_uri": "s3://example-bucket/uploads/image/example.jpg",
        }
    ]


def test_run_ocr_item_reports_success_model_and_description_marker():
    text = f"Titolo\n\n{DESC_MARKER} schema della figura]]"
    loader = FakeLoader(
        {
            "text": text,
            "completion_model": "gemini-3.1-flash-lite",
            "completion_model_provider": "google",
            "prompt_tokens": 10,
            "completion_tokens": 20,
        }
    )
    item = {
        "row_number": 1,
        "source_path": "uploads/image/example.jpg",
        "s3_uri": "s3://example-bucket/uploads/image/example.jpg",
    }

    result = run_ocr_item(item, loader)

    assert loader.seen_inputs == [["s3://example-bucket/uploads/image/example.jpg"]]
    assert result["success"] is True
    assert result["completion_model"] == "gemini-3.1-flash-lite"
    assert result["completion_model_provider"] == "google"
    assert result["has_image_description"] is True
    assert result["prompt_tokens"] == 10
    assert result["completion_tokens"] == 20
    assert result["error"] == ""
    assert result["text_char_count"] == len(text)


def test_extract_image_descriptions_returns_complete_desc_blocks():
    text = (
        "Intro\n"
        "[[DESC: primo schema con frecce]]\n"
        "Testo OCR\n"
        "[[DESC: seconda immagine\ncon dettaglio su due righe]]"
    )

    assert extract_image_descriptions(text) == [
        "[[DESC: primo schema con frecce]]",
        "[[DESC: seconda immagine\ncon dettaglio su due righe]]",
    ]


def test_run_ocr_item_reports_description_texts():
    text = "Titolo\n[[DESC: schema della figura]]\n[[DESC: foto del documento]]"
    loader = FakeLoader(
        {
            "text": text,
            "completion_model": "gemini-3.1-flash-lite",
            "completion_model_provider": "google",
        }
    )
    item = {
        "row_number": 1,
        "source_path": "uploads/image/example.jpg",
        "s3_uri": "s3://example-bucket/uploads/image/example.jpg",
    }

    result = run_ocr_item(item, loader)

    assert result["has_image_description"] is True
    assert result["image_descriptions"] == "[[DESC: schema della figura]]\n[[DESC: foto del documento]]"


def test_run_ocr_item_reads_model_metadata_from_output_list():
    loader = FakeLoader(
        {
            "text": "Testo trascritto",
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "output_list": [
                {
                    "completion_model": "gemini-3-flash-preview",
                    "completion_model_provider": "google",
                    "fallback_from_model": "gemini-3.1-flash-lite-preview",
                    "fallback_to_model": "gemini-3-flash-preview",
                    "fallback_reason": "retry",
                    "prompt_variant": "non_literal_fallback",
                    "fallback_from_prompt_variant": "default",
                    "fallback_to_prompt_variant": "non_literal_fallback",
                }
            ],
        }
    )
    item = {
        "row_number": 1,
        "source_path": "uploads/image/example.jpg",
        "s3_uri": "s3://example-bucket/uploads/image/example.jpg",
    }

    result = run_ocr_item(item, loader)

    assert result["completion_model"] == "gemini-3-flash-preview"
    assert result["completion_model_provider"] == "google"
    assert result["fallback_from_model"] == "gemini-3.1-flash-lite-preview"
    assert result["fallback_to_model"] == "gemini-3-flash-preview"
    assert result["fallback_reason"] == "retry"
    assert result["prompt_variant"] == "non_literal_fallback"
    assert result["fallback_from_prompt_variant"] == "default"
    assert result["fallback_to_prompt_variant"] == "non_literal_fallback"


def test_run_ocr_item_reports_failure_without_raising():
    loader = FakeLoader(error=RuntimeError("network unavailable"))
    item = {
        "row_number": 1,
        "source_path": "uploads/image/example.jpg",
        "s3_uri": "s3://example-bucket/uploads/image/example.jpg",
    }

    result = run_ocr_item(item, loader)

    assert result["success"] is False
    assert result["completion_model"] == ""
    assert result["has_image_description"] is False
    assert result["error"] == "network unavailable"


def test_write_report_writes_csv_with_expected_fields(tmp_path):
    output_path = tmp_path / "report.csv"
    rows = [
        {
            "row_number": 1,
            "source_path": "uploads/image/example.jpg",
            "s3_uri": "s3://example-bucket/uploads/image/example.jpg",
            "success": True,
            "completion_model": "gemini-3.1-flash-lite",
            "completion_model_provider": "google",
            "fallback_from_model": "",
            "fallback_to_model": "",
            "fallback_reason": "",
            "prompt_variant": "default",
            "fallback_from_prompt_variant": "",
            "fallback_to_prompt_variant": "",
            "has_image_description": False,
            "image_descriptions": "[[DESC: schema della figura]]",
            "elapsed_seconds": 0.123,
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "text_char_count": 30,
            "error": "",
        }
    ]

    write_report(rows, output_path)

    with output_path.open(newline="", encoding="utf-8") as csv_file:
        written_rows = list(csv.DictReader(csv_file))

    assert written_rows[0]["s3_uri"] == "s3://example-bucket/uploads/image/example.jpg"
    assert written_rows[0]["completion_model"] == "gemini-3.1-flash-lite"
    assert written_rows[0]["prompt_variant"] == "default"
    assert written_rows[0]["has_image_description"] == "False"
    assert written_rows[0]["image_descriptions"] == "[[DESC: schema della figura]]"


def test_main_dry_run_does_not_create_report_or_call_loader(tmp_path, monkeypatch):
    csv_path = tmp_path / "activity.csv"
    output_path = tmp_path / "report.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["Transcript Input Source"])
        writer.writeheader()
        writer.writerow({"Transcript Input Source": "uploads/image/example.jpg"})

    def fail_build_loader(*args, **kwargs):
        raise AssertionError("dry run must not create the OCR loader")

    monkeypatch.setattr("test_transcribe_s3_images_from_csv_script.build_loader", fail_build_loader)

    exit_code = main(["--csv-path", str(csv_path), "--output-path", str(output_path), "--dry-run"])

    assert exit_code == 0
    assert not output_path.exists()
