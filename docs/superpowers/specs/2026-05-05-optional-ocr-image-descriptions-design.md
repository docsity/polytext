# Optional OCR Image Descriptions Design

## Context

Polytext currently has OCR prompts in `polytext/prompts/ocr.py` for Markdown and plain text output. These prompts extract readable text and preserve document structure, but they do not ask the vision model to describe meaningful non-text images such as diagrams, charts, schemas, maps, screenshots, or photos.

Some documents rely on images for essential context. OCR output should be able to preserve that context when requested, without changing default behavior for existing callers.

## Goal

Add an opt-in OCR behavior that inserts brief, functional image descriptions into the transcribed text.

The option should be exposed from `BaseLoader` so the main user-facing loader API can enable it:

```python
BaseLoader(include_image_descriptions=True)
```

The default must remain `False`.

## Behavior

When image descriptions are enabled, OCR output should include descriptions for meaningful non-text visual content using exactly this marker:

```text
[Image description: ...]
```

The marker should be inserted in the reading order where the image appears. If the image visually interrupts a sentence, the marker should be placed after the nearest complete sentence or phrase, then the surrounding text should continue.

Descriptions should be brief and functional. For simple photos, decorative illustrations, or small visual cues, they should stay concise. For diagrams, schemas, charts, maps, screenshots, and visual tables, they should include all meaningful information needed to understand the image context, including labels, relationships, axes, trends, hierarchy, and text inside the image when it is not already transcribed elsewhere.

Purely decorative marks, borders, logos, and icons should not be described unless they carry document meaning.

## API And Data Flow

Add `include_image_descriptions: bool = False` to `BaseLoader.__init__` and store it on the instance.

Pass the value through the OCR paths:

- `BaseLoader.init_loader_class(...)` passes it to `OCRLoader` for image inputs.
- `BaseLoader.init_loader_class(...)` passes it to `DocumentOCRLoader` when document OCR fallback is used.
- `OCRLoader` passes it to `polytext.converter.ocr_to_text.get_ocr`.
- `DocumentOCRLoader` passes it to the selected document OCR backend.
- Google image OCR and Google document OCR converters accept and store it.
- Azure image OCR and Azure document OCR converters accept it as well for consistent public behavior.

Prompt selection should remain centralized around `polytext/prompts/ocr.py`. The converters should select the base Markdown or plain text prompt, then augment it only when `include_image_descriptions=True`.

## Prompt Design

Add a shared image-description instruction block in `polytext/prompts/ocr.py`, plus a helper that appends it to either OCR prompt only when enabled.

The helper keeps prompt formatting consistent and avoids duplicating the same instructions in every converter.

## Testing

Unit tests should avoid live OCR calls. They should verify:

- The prompt helper returns the base prompt unchanged when image descriptions are disabled.
- The prompt helper appends image-description instructions when enabled.
- `BaseLoader` stores `include_image_descriptions` and passes it into image OCR and document OCR loader construction.
- OCR converter fallback instances preserve the image-description setting.

## Out Of Scope

This change does not evaluate real model quality, tune description length dynamically, or add a separate output field for image descriptions. It only adds opt-in prompt behavior and API propagation.
