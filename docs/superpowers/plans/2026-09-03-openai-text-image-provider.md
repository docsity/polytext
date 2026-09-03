# OpenAI Text and Image Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Polytext use direct OpenAI models, initially `gpt-5.6-luna`, for text formatting, chunk merging, single-image OCR, and multipage document OCR.

**Architecture:** Add a provider-neutral multimodal generation adapter over Google GenAI and the OpenAI Responses API. Existing converters keep ownership of chunking, prompts, preprocessing, fallback decisions, and output formatting; they delegate only inference and response normalization, and propagate one provider/model through every call in a flow.

**Tech Stack:** Python 3, `google-genai`, `openai==2.26.0`, `retry`, `unittest`, PyMuPDF/FFmpeg image preprocessing.

**Spec:** `docs/superpowers/specs/2026-09-03-openai-text-image-provider-design.md`

## Global Constraints

- Google remains the default provider and retains existing behavior.
- Direct OpenAI uses `llm_api_key` when provided and otherwise lets the SDK read `OPENAI_API_KEY`.
- The default direct OpenAI model is exactly `gpt-5.6-luna`.
- Azure OpenAI remains a separate document backend and its configuration contract is unchanged.
- OpenAI failures never cause an implicit fallback to Google, Azure, or another model.
- Audio, video, and YouTube behavior is unchanged.
- Do not stage or commit `tests/test_get_audio_transcript_from_gcs.py`, `tests/test_get_document_ocr.py`, or `tests/test_get_document_text.py`.

---

### Task 1: Provider-neutral multimodal adapter

**Files:**
- Create: `polytext/llm/__init__.py`
- Create: `polytext/llm/multimodal.py`
- Create: `tests/test_multimodal_llm.py`

**Interfaces:**
- Produces: `normalize_provider(provider: str) -> str`
- Produces: `GenerationResult(text: str, prompt_tokens: int, completion_tokens: int, model: str, provider: str, finish_reason: str | None)`
- Produces: `MultimodalLLM(model: str, provider: str = "google", api_key: str | None = None, timeout_minutes: int | None = None)`
- Produces: `MultimodalLLM.generate_text(instructions: str, input_text: str, max_output_tokens: int | None = None, temperature: float | None = None) -> GenerationResult`
- Produces: `MultimodalLLM.generate_image(instructions: str, image_data: bytes, mime_type: str, max_output_tokens: int | None = None, temperature: float | None = None) -> GenerationResult`

- [ ] **Step 1: Write failing provider and text-response tests**

Create `tests/test_multimodal_llm.py` with `unittest` cases that patch only external SDK constructors. Cover aliases, rejection of unknown providers, explicit key forwarding, absence of an explicit key, the OpenAI text payload, and normalized usage:

```python
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from polytext.llm.multimodal import MultimodalLLM, normalize_provider


class TestMultimodalLLM(unittest.TestCase):
    def test_normalizes_supported_provider_aliases(self):
        self.assertEqual(normalize_provider("gemini"), "google")
        self.assertEqual(normalize_provider("OPENAI"), "openai")

    def test_rejects_unknown_provider(self):
        with self.assertRaisesRegex(ValueError, "Unsupported LLM provider"):
            normalize_provider("unknown")

    @patch("polytext.llm.multimodal.OpenAI")
    def test_openai_text_generation_normalizes_response(self, openai_cls):
        response = SimpleNamespace(
            output_text="clean text",
            usage=SimpleNamespace(input_tokens=17, output_tokens=9),
            status="completed",
            incomplete_details=None,
        )
        openai_cls.return_value.responses.create.return_value = response

        result = MultimodalLLM(
            model="gpt-5.6-luna", provider="openai", api_key="explicit-key"
        ).generate_text("Clean faithfully", "raw text", max_output_tokens=8000)

        self.assertEqual(result.text, "clean text")
        self.assertEqual(result.prompt_tokens, 17)
        self.assertEqual(result.completion_tokens, 9)
        self.assertEqual(result.provider, "openai")
        openai_cls.assert_called_once_with(api_key="explicit-key")
        openai_cls.return_value.responses.create.assert_called_once_with(
            model="gpt-5.6-luna",
            instructions="Clean faithfully",
            input="raw text",
            max_output_tokens=8000,
            reasoning={"effort": "none"},
        )
```

- [ ] **Step 2: Run the tests and verify the missing-module failure**

Run: `.venv/bin/python -m unittest tests.test_multimodal_llm`

Expected: ERROR with `ModuleNotFoundError: No module named 'polytext.llm'`.

- [ ] **Step 3: Implement provider normalization, client construction, and text generation**

Implement the focused adapter in `polytext/llm/multimodal.py`:

```python
from dataclasses import dataclass

from google import genai
from google.genai import types
from openai import OpenAI


@dataclass(frozen=True)
class GenerationResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str
    finish_reason: str | None = None


def normalize_provider(provider: str) -> str:
    normalized = (provider or "google").strip().lower()
    aliases = {"google": "google", "gemini": "google", "openai": "openai"}
    if normalized not in aliases:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return aliases[normalized]
```

Construct `OpenAI(api_key=api_key)` only when a key is supplied and `OpenAI()` otherwise. For OpenAI text calls use `responses.create(model=..., instructions=..., input=..., max_output_tokens=..., reasoning={"effort": "none"})`, omitting optional arguments whose value is `None`. For Google, build the existing `GenerateContentConfig`, call `client.models.generate_content`, and normalize `usage_metadata`.

- [ ] **Step 4: Add a failing OpenAI image-payload test**

Use literal bytes and assert the observable Responses API request:

```python
    @patch("polytext.llm.multimodal.OpenAI")
    def test_openai_image_generation_sends_a_data_url(self, openai_cls):
        openai_cls.return_value.responses.create.return_value = SimpleNamespace(
            output_text="visible words",
            usage=SimpleNamespace(input_tokens=31, output_tokens=4),
            status="completed",
            incomplete_details=None,
        )

        result = MultimodalLLM("gpt-5.6-luna", "openai").generate_image(
            "Transcribe", b"image-bytes", "image/png", max_output_tokens=8192
        )

        request = openai_cls.return_value.responses.create.call_args.kwargs
        image_part = request["input"][0]["content"][1]
        self.assertEqual(image_part["type"], "input_image")
        self.assertEqual(
            image_part["image_url"],
            "data:image/png;base64,aW1hZ2UtYnl0ZXM=",
        )
        self.assertEqual(result.text, "visible words")
```

- [ ] **Step 5: Run the image test and verify it fails because `generate_image` is absent**

Run: `.venv/bin/python -m unittest tests.test_multimodal_llm.TestMultimodalLLM.test_openai_image_generation_sends_a_data_url`

Expected: FAIL/ERROR identifying the missing `generate_image` behavior.

- [ ] **Step 6: Implement image generation and terminal-response validation**

Encode bytes with `base64.b64encode`, build an OpenAI `input_image` data URL payload, and reject empty output or `status == "incomplete"` with a provider-neutral `LLMGenerationError`. Add tests proving OpenAI authentication/permission/bad-request exceptions are raised immediately while timeout, connection, rate-limit, and 5xx exceptions are eligible for the adapter's bounded retry policy.

- [ ] **Step 7: Run adapter tests and the existing dependency import tests**

Run: `.venv/bin/python -m unittest tests.test_multimodal_llm`

Expected: all adapter tests PASS without network calls.

- [ ] **Step 8: Commit the adapter**

```bash
git add polytext/llm/__init__.py polytext/llm/multimodal.py tests/test_multimodal_llm.py
git commit -m "feat: add multimodal LLM provider adapter"
```

### Task 2: OpenAI text conversion and provider-consistent merging

**Files:**
- Modify: `polytext/converter/text_to_md.py`
- Modify: `polytext/converter/beautiful_text.py`
- Modify: `polytext/processor/text_merger.py`
- Modify: `polytext/loader/plain_text.py`
- Modify: `polytext/loader/base.py`
- Create: `tests/test_openai_text_flows.py`

**Interfaces:**
- Consumes: `MultimodalLLM.generate_text(...) -> GenerationResult`
- Produces: `text_to_md(..., model: str | None = None, model_provider: str = "google") -> dict`
- Produces: `PlainTextLoader(..., model: str | None = None, model_provider: str = "google")`
- Preserves: `TextMerger(completion_model=..., completion_model_provider=..., llm_api_key=...)`

- [ ] **Step 1: Write failing end-to-end unit tests for provider propagation**

In `tests/test_openai_text_flows.py`, construct a real `PlainTextLoader` with a fake `MultimodalLLM` injected by patching its constructor. Feed a short text and assert the returned metadata says `gpt-5.6-luna`/`openai`. Feed text large enough for two deterministic chunks and assert both chunk processing and `TextMerger` use the same provider/model. Add a `BaseLoader.get_beautiful_text` test showing its converter receives `provider="openai"`, `model="gpt-5.6-luna"`, and the explicit key.

- [ ] **Step 2: Run the new text-flow tests and verify provider propagation failures**

Run: `.venv/bin/python -m unittest tests.test_openai_text_flows`

Expected: FAIL because `PlainTextLoader` and `BaseLoader.get_beautiful_text` currently discard provider/model and the converters call Google directly.

- [ ] **Step 3: Route text converter calls through the adapter**

Update `TextToMdConverter.process_chunk`, `BeautifulTextConverter.process_chunk`, and `TextMerger.merge_texts_with_llm` to consume `GenerationResult`:

```python
generation = client.generate_text(
    instructions=prompt_template,
    input_text=chunk_text,
    max_output_tokens=self.max_llm_tokens,
)
return {
    "transcript": generation.text,
    "completion_tokens": generation.completion_tokens,
    "prompt_tokens": generation.prompt_tokens,
}
```

Each converter's `get_client` returns `MultimodalLLM(model=..., provider=..., api_key=..., timeout_minutes=...)`. Preserve existing public result keys.

- [ ] **Step 4: Propagate configuration through loaders and merge**

Pass `model` and `model_provider` through `text_to_md`, `PlainTextLoader`, `BaseLoader.init_loader_class`, and `BaseLoader.get_beautiful_text`. When `provider="openai"` and no explicit model is supplied, resolve `gpt-5.6-luna`; otherwise preserve the current Google defaults. Instantiate merge as:

```python
TextMerger(
    completion_model=self.model,
    completion_model_provider=self.model_provider,
    llm_api_key=self.llm_api_key,
)
```

- [ ] **Step 5: Run text and merge regression tests**

Run: `.venv/bin/python -m unittest tests.test_openai_text_flows tests.test_text_merger_diagnostics tests.test_pain_text`

Expected: all tests PASS; existing tests still identify Google as the default.

- [ ] **Step 6: Commit text support**

```bash
git add polytext/converter/text_to_md.py polytext/converter/beautiful_text.py polytext/processor/text_merger.py polytext/loader/plain_text.py polytext/loader/base.py tests/test_openai_text_flows.py
git commit -m "feat: support OpenAI in text conversion flows"
```

### Task 3: Direct OpenAI single-image OCR

**Files:**
- Modify: `polytext/converter/ocr_to_text.py`
- Modify: `polytext/loader/ocr.py`
- Modify: `polytext/loader/base.py`
- Create: `tests/test_openai_image_ocr.py`

**Interfaces:**
- Consumes: `MultimodalLLM.generate_image(...) -> GenerationResult`
- Produces: `get_ocr(..., ocr_model_provider: str = "google") -> dict`
- Preserves: `OCRToTextConverter(..., ocr_model_provider=..., ocr_model=...)`

- [ ] **Step 1: Write failing OpenAI OCR behavior tests**

Create a temporary PNG fixture with literal bytes, patch image preprocessing only where necessary, and replace `MultimodalLLM.generate_image` at the external call boundary. Assert that a real `OCRToTextConverter` returns text, normalized tokens, `completion_model="gpt-5.6-luna"`, and `completion_model_provider="openai"`. Add cases for `no readable text present`, empty output, and an OpenAI failure proving no Gemini fallback constructor is called.

- [ ] **Step 2: Run the tests and verify the Google-only failures**

Run: `.venv/bin/python -m unittest tests.test_openai_image_ocr`

Expected: FAIL because `OCRToTextConverter.get_ocr` constructs `genai.Client` and `OCRLoader` filters out non-Gemini model names.

- [ ] **Step 3: Route single-image inference by provider**

Pass `ocr_model_provider` through the `get_ocr` convenience function and loader. Preserve model names for OpenAI instead of applying the current `startswith("gemini")` filter. After existing MIME detection and preprocessing, read image bytes and call:

```python
generation = MultimodalLLM(
    model=self.ocr_model,
    provider=self.ocr_model_provider,
    api_key=self.llm_api_key,
    timeout_minutes=self.timeout_minutes,
).generate_image(
    instructions=prompt_template,
    image_data=image_data,
    mime_type=mime_type,
    max_output_tokens=self.max_output_tokens,
    temperature=temperature,
)
```

Keep Gemini's existing recitation, max-token, repetition, prompt retry, and fallback behavior on the Google branch. OpenAI errors leave the OpenAI branch and never call `run_fallback` with Gemini models.

- [ ] **Step 4: Run OpenAI and Gemini OCR suites**

Run: `.venv/bin/python -m unittest tests.test_openai_image_ocr tests.test_ocr_fallbacks tests.test_ocr_image_descriptions`

Expected: all tests PASS.

- [ ] **Step 5: Commit image OCR support**

```bash
git add polytext/converter/ocr_to_text.py polytext/loader/ocr.py polytext/loader/base.py tests/test_openai_image_ocr.py
git commit -m "feat: support direct OpenAI image OCR"
```

### Task 4: Direct OpenAI multipage document OCR

**Files:**
- Modify: `polytext/converter/document_ocr_to_text.py`
- Modify: `polytext/loader/document_ocr.py`
- Modify: `polytext/loader/base.py`
- Create: `tests/test_openai_document_ocr.py`
- Modify: `tests/test_ocr_fallbacks.py`

**Interfaces:**
- Consumes: `MultimodalLLM.generate_image(...) -> GenerationResult`
- Produces: `get_document_ocr(..., ocr_model_provider: str = "google") -> dict`
- Preserves: `DocumentOCRLoader(ocr_provider=..., ocr_model=...)`

- [ ] **Step 1: Write failing loader-routing and ordered-page tests**

Test `_select_document_ocr_fn` accepts `openai`, rejects unknown providers with an updated message, and leaves all Azure aliases unchanged. Build a two-page converter fixture by patching PDF rendering to return two named temporary images, return distinct adapter results, and assert final text/page chunks preserve page order and aggregate literal token totals. Add one failing-page case for each `allow_partial_ocr_failures` value.

- [ ] **Step 2: Run the document tests and verify OpenAI is rejected**

Run: `.venv/bin/python -m unittest tests.test_openai_document_ocr`

Expected: FAIL with `Invalid ocr_provider='openai'` or a Google-client call.

- [ ] **Step 3: Generalize the existing document converter's inference boundary**

Add `ocr_model_provider` to `get_document_ocr` and `DocumentOCRToTextConverter`. Keep existing PDF page rendering, parallel page scheduling, ordering, aggregation, cleanup, and partial-failure logic. Replace only the per-page generation call with `MultimodalLLM.generate_image`, using the rendered page MIME type and the existing OCR prompt.

Guard all Gemini-only output checks and fallback methods with `self.ocr_model_provider == "google"`. OpenAI incomplete/empty responses become the same page failure type consumed by the existing partial-failure policy.

- [ ] **Step 4: Add direct OpenAI routing to `DocumentOCRLoader`**

Map `ocr_provider="openai"` to the generalized document converter and call it with:

```python
result_dict = get_document_ocr_direct(
    document_for_ocr=temp_file_path,
    markdown_output=self.markdown_output,
    llm_api_key=self.llm_api_key,
    target_size=self.target_size,
    page_range=self.page_range,
    timeout_minutes=self.timeout_minutes,
    ocr_model=self.ocr_model or "gpt-5.6-luna",
    ocr_model_provider="openai",
    max_output_tokens=self.max_output_tokens,
    include_image_descriptions=self.include_image_descriptions,
    allow_partial_ocr_failures=self.allow_partial_ocr_failures,
)
```

Do not modify the Azure function or Azure arguments.

- [ ] **Step 5: Run document OCR regression tests**

Run: `.venv/bin/python -m unittest tests.test_openai_document_ocr tests.test_ocr_fallbacks tests.test_ocr_image_descriptions tests.test_get_document_ocr_azure_oai`

Expected: all tests PASS and Azure routing still selects its existing backend.

- [ ] **Step 6: Commit document OCR support**

```bash
git add polytext/converter/document_ocr_to_text.py polytext/loader/document_ocr.py polytext/loader/base.py tests/test_openai_document_ocr.py tests/test_ocr_fallbacks.py
git commit -m "feat: support direct OpenAI document OCR"
```

### Task 5: Public contract regression and opt-in real API smoke tests

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: public `BaseLoader(provider="openai", ocr_model="gpt-5.6-luna", llm_api_key=...)`
- Produces: documented text, image, and forced/document OCR examples.

- [ ] **Step 1: Run the public-contract tests created in the preceding tasks**

Run the deterministic `BaseLoader` cases from Tasks 2–4 that exercise raw text, an image path, and a forced-OCR PDF path. These tests patch storage/MIME/external inference only and keep the real loader factory and public result construction active.

- [ ] **Step 2: Verify all public paths retain OpenAI configuration**

Run: `.venv/bin/python -m unittest tests.test_openai_text_flows tests.test_openai_image_ocr tests.test_openai_document_ocr`

Expected: PASS, demonstrating every public path retains the selected provider and model.

- [ ] **Step 3: Document usage**

Add README examples using environment credentials:

```python
loader = BaseLoader(
    provider="openai",
    ocr_model="gpt-5.6-luna",
    source="local",
)
result = loader.get_text(input_list=[input_value])
```

Document that `OPENAI_API_KEY` is read when `llm_api_key` is omitted, that `llm_api_key` takes precedence, and that OpenAI support applies to text, images, and document OCR but not audio/YouTube.

- [ ] **Step 4: Run the full deterministic unit suite**

Run: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`

Expected: PASS. If existing manual/network tests are discovered and require external services, record them separately and run the complete deterministic subset plus every suite named in Tasks 1–4.

- [ ] **Step 5: Run opt-in real Luna smoke tests when credentials are available**

With `OPENAI_API_KEY` set, run one short raw-text input, one local PNG/JPEG, and a two-page PDF through `BaseLoader(provider="openai", ocr_model="gpt-5.6-luna", source="local")`. Verify non-empty output, provider/model metadata, ordered pages, and non-negative token counts. Do not write credentials or full private input contents to logs.

- [ ] **Step 6: Review the final diff and excluded files**

Run: `git diff --check`

Run: `git status --short`

Expected: the three user-modified manual test files remain unstaged and absent from every feature commit.

- [ ] **Step 7: Commit documentation and contract tests**

```bash
git add README.md
git commit -m "docs: document direct OpenAI transcription"
```
