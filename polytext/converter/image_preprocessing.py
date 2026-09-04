"""Provider-aware image preparation shared by direct OCR converters."""

import logging
import mimetypes
import os
import tempfile
from dataclasses import dataclass

import ffmpeg

from ..llm import normalize_provider

logger = logging.getLogger(__name__)

GEMINI_SUPPORTED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
}
OPENAI_SUPPORTED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}
HEIF_MIME_TYPES = {"image/heic", "image/heif"}
OPENAI_MAX_IMAGE_SIZE_MB = 20


@dataclass(frozen=True)
class PreparedImage:
    """Image path and metadata after provider-specific preparation."""

    path: str
    mime_type: str
    file_size: int
    is_temporary: bool


def _convert_heif_to_png(input_path: str, output_path: str, target_size_mb: int) -> None:
    """Convert the first HEIC/HEIF frame to an EXIF-corrected PNG."""
    try:
        from PIL import Image, ImageOps
        from pillow_heif import register_heif_opener
    except ImportError as error:
        raise RuntimeError(
            "HEIC/HEIF conversion requires the 'pillow-heif' dependency"
        ) from error

    register_heif_opener()
    with Image.open(input_path) as source:
        source.seek(0)
        image = ImageOps.exif_transpose(source)
        target_size = target_size_mb * 1024 * 1024
        original_size = os.path.getsize(input_path)
        if original_size > target_size:
            ratio = (target_size / original_size) ** 0.5
            image = image.resize(
                (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
            )
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        image.save(output_path, format="PNG", optimize=True)


def convert_image_to_png(
    input_path: str,
    target_size_mb: int,
    mime_type: str | None = None,
) -> str:
    """Convert an image to a temporary PNG, reducing oversized inputs.

    HEIC and HEIF use ``pillow-heif``. Other formats use FFmpeg and select
    only the first frame, making animated GIF handling deterministic for OCR.
    The caller owns the returned temporary file.
    """
    resolved_mime_type = mime_type or mimetypes.guess_type(input_path)[0]
    fd, output_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        if resolved_mime_type in HEIF_MIME_TYPES:
            _convert_heif_to_png(input_path, output_path, target_size_mb)
        else:
            original_size = os.path.getsize(input_path)
            target_size = target_size_mb * 1024 * 1024
            output_options = {
                "compression_level": 9,
                "threads": 0,
                "loglevel": "error",
                "vframes": 1,
            }
            if original_size > target_size:
                ratio = (target_size / original_size) ** 0.5
                output_options["vf"] = f"scale=iw*{ratio}:ih*{ratio}"
            (
                ffmpeg.input(input_path)
                .output(output_path, **output_options)
                .run(quiet=True, overwrite_output=True)
            )
        return output_path
    except Exception as error:
        if os.path.exists(output_path):
            os.remove(output_path)
        logger.exception("Image conversion failed for %s", input_path)
        raise RuntimeError(f"Image conversion failed: {error}") from error


def prepare_image_for_ocr(
    input_path: str,
    provider: str,
    target_size_mb: int,
) -> PreparedImage:
    """Prepare an image according to the selected OCR provider.

    Gemini retains the historical ``target_size_mb`` threshold. Direct OpenAI
    preserves compatible PNG, JPEG, and WebP inputs up to 20 MB, while other
    formats and larger inputs are converted to PNG.
    """
    resolved_provider = normalize_provider(provider)
    mime_type = mimetypes.guess_type(input_path)[0]
    file_size = os.path.getsize(input_path)
    if resolved_provider == "openai":
        supported_types = OPENAI_SUPPORTED_MIME_TYPES
        conversion_target_mb = OPENAI_MAX_IMAGE_SIZE_MB
    else:
        supported_types = GEMINI_SUPPORTED_MIME_TYPES
        conversion_target_mb = target_size_mb

    requires_conversion = (
        mime_type not in supported_types
        or file_size > conversion_target_mb * 1024 * 1024
    )
    if not requires_conversion:
        logger.info(
            "Keeping original image for provider=%s: mime_type=%s, size=%.2f MB",
            resolved_provider,
            mime_type,
            file_size / (1024 * 1024),
        )
        return PreparedImage(input_path, mime_type or "", file_size, False)

    logger.info(
        "Converting image for provider=%s: mime_type=%s, size=%.2f MB, target=%s MB",
        resolved_provider,
        mime_type,
        file_size / (1024 * 1024),
        conversion_target_mb,
    )
    converted_path = convert_image_to_png(
        input_path,
        target_size_mb=conversion_target_mb,
        mime_type=mime_type,
    )
    return PreparedImage(
        converted_path,
        "image/png",
        os.path.getsize(converted_path),
        True,
    )
