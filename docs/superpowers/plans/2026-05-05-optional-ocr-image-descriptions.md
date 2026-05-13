# Optional OCR Image Descriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `BaseLoader(include_image_descriptions=True)` flag that asks OCR prompts to include concise, functional image descriptions inline.

**Architecture:** Keep the prompt text centralized in `polytext/prompts/ocr.py` and append image-description instructions only when requested. Thread the flag from `BaseLoader` through OCR loaders and converters, including fallback converter construction.

**Tech Stack:** Python, pytest/unittest, existing Gemini and Azure OCR converter classes.

---

## File Structure

- Modify `polytext/prompts/ocr.py`: add the shared image-description instruction block and a helper function.
- Modify `polytext/loader/base.py`: accept and pass `include_image_descriptions`.
- Modify `polytext/loader/ocr.py`: store and pass the flag to image OCR.
- Modify `polytext/loader/document_ocr.py`: store and pass the flag to Google and Azure document OCR.
- Modify `polytext/converter/ocr_to_text.py`: accept the flag, build prompts through the helper, preserve it in fallback converters.
- Modify `polytext/converter/document_ocr_to_text.py`: same for Google document OCR.
- Modify `polytext/converter/ocr_to_text_azure_oai.py`: same for Azure image OCR.
- Modify `polytext/converter/document_ocr_to_text_azure_oai.py`: same for Azure document OCR.
- Create or modify `tests/test_ocr_image_descriptions.py`: focused unit tests without live OCR calls.

### Task 1: Prompt Helper

**Files:**
- Modify: `polytext/prompts/ocr.py`
- Test: `tests/test_ocr_image_descriptions.py`

- [ ] **Step 1: Write failing prompt helper tests**

```python
from polytext.prompts.ocr import (
    OCR_IMAGE_DESCRIPTION_INSTRUCTIONS,
    OCR_TO_MARKDOWN_PROMPT,
    build_ocr_prompt,
)


def test_build_ocr_prompt_leaves_base_prompt_unchanged_when_disabled():
    assert build_ocr_prompt(OCR_TO_MARKDOWN_PROMPT, include_image_descriptions=False) == OCR_TO_MARKDOWN_PROMPT


def test_build_ocr_prompt_appends_image_description_instructions_when_enabled():
    prompt = build_ocr_prompt(OCR_TO_MARKDOWN_PROMPT, include_image_descriptions=True)

    assert prompt.startswith(OCR_TO_MARKDOWN_PROMPT.strip())
    assert "[Image description:" in prompt
    assert OCR_IMAGE_DESCRIPTION_INSTRUCTIONS.strip() in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ocr_image_descriptions.py -q`
Expected: FAIL because `OCR_IMAGE_DESCRIPTION_INSTRUCTIONS` and `build_ocr_prompt` do not exist.

- [ ] **Step 3: Implement prompt helper**

```python
OCR_IMAGE_DESCRIPTION_INSTRUCTIONS = """
Image description instructions:
- When meaningful non-text visual content is present, insert a concise description using exactly this format: [Image description: ...].
- Insert the description where the image appears in the reading order.
- If an image visually interrupts a sentence, place the description after the nearest complete sentence or phrase, then continue with the remaining text.
- Keep descriptions brief and functional.
- For diagrams, schemas, charts, maps, screenshots, and visual tables, include all meaningful information needed to understand the context, including labels, relationships, axes, trends, hierarchy, and text inside the image when it is not already transcribed elsewhere.
- Do not describe purely decorative marks, borders, logos, or icons unless they carry document meaning.
"""


def build_ocr_prompt(base_prompt: str, include_image_descriptions: bool = False) -> str:
    if not include_image_descriptions:
        return base_prompt
    return f"{base_prompt.rstrip()}\n\n{OCR_IMAGE_DESCRIPTION_INSTRUCTIONS.strip()}\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ocr_image_descriptions.py -q`
Expected: PASS.

### Task 2: Loader Propagation

**Files:**
- Modify: `polytext/loader/base.py`
- Modify: `polytext/loader/ocr.py`
- Modify: `polytext/loader/document_ocr.py`
- Test: `tests/test_ocr_image_descriptions.py`

- [ ] **Step 1: Write failing loader propagation tests**

```python
from polytext.loader import BaseLoader
from polytext.loader.document_ocr import DocumentOCRLoader
from polytext.loader.ocr import OCRLoader


def test_base_loader_stores_include_image_descriptions():
    loader = BaseLoader(source="local", include_image_descriptions=True)

    assert loader.include_image_descriptions is True


def test_base_loader_passes_include_image_descriptions_to_image_ocr_loader():
    loader = BaseLoader(source="local", include_image_descriptions=True)
    ocr_loader = loader.init_loader_class(
        input="/tmp/example.png",
        storage_client={},
        llm_api_key=None,
        source="local",
    )

    assert isinstance(ocr_loader, OCRLoader)
    assert ocr_loader.include_image_descriptions is True


def test_base_loader_passes_include_image_descriptions_to_document_ocr_fallback_loader():
    loader = BaseLoader(source="local", include_image_descriptions=True)
    document_ocr_loader = loader.init_loader_class(
        input="/tmp/example.pdf",
        storage_client={},
        llm_api_key=None,
        is_document_fallback=True,
        source="local",
    )

    assert isinstance(document_ocr_loader, DocumentOCRLoader)
    assert document_ocr_loader.include_image_descriptions is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ocr_image_descriptions.py -q`
Expected: FAIL because the loaders do not expose or pass the new flag.

- [ ] **Step 3: Implement loader propagation**

Add `include_image_descriptions: bool = False` to `BaseLoader.__init__`, store `self.include_image_descriptions`, and pass it into `OCRLoader` and `DocumentOCRLoader` constructor calls. Add matching constructor parameters and instance fields in both loaders, then pass the flag into the OCR converter functions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ocr_image_descriptions.py -q`
Expected: PASS.

### Task 3: Converter Prompt Selection And Fallback Propagation

**Files:**
- Modify: `polytext/converter/ocr_to_text.py`
- Modify: `polytext/converter/document_ocr_to_text.py`
- Modify: `polytext/converter/ocr_to_text_azure_oai.py`
- Modify: `polytext/converter/document_ocr_to_text_azure_oai.py`
- Test: `tests/test_ocr_image_descriptions.py`

- [ ] **Step 1: Write failing converter tests**

```python
from polytext.converter.document_ocr_to_text import DocumentOCRToTextConverter
from polytext.converter.ocr_to_text import OCRToTextConverter


def test_google_ocr_converter_builds_augmented_markdown_prompt():
    converter = OCRToTextConverter(include_image_descriptions=True)

    prompt = converter._build_prompt_template()

    assert "[Image description:" in prompt


def test_google_document_ocr_converter_builds_augmented_markdown_prompt():
    converter = DocumentOCRToTextConverter(include_image_descriptions=True)

    prompt = converter._build_prompt_template()

    assert "[Image description:" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ocr_image_descriptions.py -q`
Expected: FAIL because converter constructors and `_build_prompt_template` do not exist.

- [ ] **Step 3: Implement converter propagation**

Add `include_image_descriptions` to converter functions and classes. Add `_build_prompt_template()` methods in Google converters and use them in `get_ocr`. Import and use `build_ocr_prompt`. Ensure fallback converter construction passes `include_image_descriptions=self.include_image_descriptions`. Apply equivalent prompt helper usage in Azure converters.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_ocr_image_descriptions.py -q`
Expected: PASS.

### Task 4: Regression Test Sweep

**Files:**
- Test only

- [ ] **Step 1: Run focused OCR fallback tests**

Run: `pytest tests/test_ocr_image_descriptions.py tests/test_ocr_fallbacks.py -q`
Expected: PASS.

- [ ] **Step 2: Run syntax compilation for touched package files**

Run: `python -m compileall polytext/prompts polytext/loader polytext/converter -q`
Expected: exit code 0.

- [ ] **Step 3: Commit implementation**

```bash
git add polytext/prompts/ocr.py polytext/loader/base.py polytext/loader/ocr.py polytext/loader/document_ocr.py polytext/converter/ocr_to_text.py polytext/converter/document_ocr_to_text.py polytext/converter/ocr_to_text_azure_oai.py polytext/converter/document_ocr_to_text_azure_oai.py tests/test_ocr_image_descriptions.py docs/superpowers/plans/2026-05-05-optional-ocr-image-descriptions.md
git commit -m "Add optional OCR image descriptions"
```
