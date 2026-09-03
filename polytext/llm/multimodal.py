import base64
from dataclasses import dataclass

from google import genai
from google.genai import types
from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError
from retry import retry


@dataclass(frozen=True)
class GenerationResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str
    finish_reason: str | None = None


class LLMGenerationError(RuntimeError):
    """Raised when an LLM returns no usable completed output."""


def normalize_provider(provider: str) -> str:
    normalized = (provider or "google").strip().lower()
    aliases = {
        "google": "google",
        "gemini": "google",
        "openai": "openai",
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return aliases[normalized]


class MultimodalLLM:
    def __init__(
        self,
        model: str,
        provider: str = "google",
        api_key: str | None = None,
        timeout_minutes: int | None = None,
    ) -> None:
        self.model = model
        self.provider = normalize_provider(provider)
        self.api_key = api_key
        self.timeout_minutes = timeout_minutes
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if self.provider == "openai":
            self._client = OpenAI(api_key=self.api_key) if self.api_key else OpenAI()
        else:
            self._client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        return self._client

    @staticmethod
    def _google_safety_settings():
        return [
            types.SafetySetting(
                category=category,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            )
            for category in (
                types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            )
        ]

    @retry(
        (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError),
        tries=5,
        delay=1,
        backoff=2,
    )
    def _create_openai_response(self, **request):
        return self._get_client().responses.create(**request)

    @staticmethod
    def _openai_result(response, model: str) -> GenerationResult:
        text = response.output_text or ""
        status = getattr(response, "status", None)
        incomplete_details = getattr(response, "incomplete_details", None)
        if status == "incomplete":
            reason = getattr(incomplete_details, "reason", "unknown")
            raise LLMGenerationError(f"OpenAI returned an incomplete response: {reason}")
        if not text.strip():
            raise LLMGenerationError("OpenAI returned an empty response")
        usage = getattr(response, "usage", None)
        return GenerationResult(
            text=text,
            prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
            completion_tokens=getattr(usage, "output_tokens", 0) or 0,
            model=model,
            provider="openai",
            finish_reason=status,
        )

    def generate_text(
        self,
        instructions: str,
        input_text: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> GenerationResult:
        client = self._get_client()
        if self.provider == "openai":
            request = {
                "model": self.model,
                "instructions": instructions,
                "input": input_text,
                "reasoning": {"effort": "none"},
            }
            if max_output_tokens is not None:
                request["max_output_tokens"] = max_output_tokens
            response = self._create_openai_response(**request)
            return self._openai_result(response, self.model)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            safety_settings=self._google_safety_settings(),
            http_options=(
                types.HttpOptions(timeout=self.timeout_minutes * 60_000)
                if self.timeout_minutes is not None
                else None
            ),
        )
        response = client.models.generate_content(
            model=self.model,
            contents=[instructions, input_text],
            config=config,
        )
        usage = response.usage_metadata
        return GenerationResult(
            text=response.text or "",
            prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            model=self.model,
            provider="google",
            finish_reason=None,
        )

    def generate_image(
        self,
        instructions: str,
        image_data: bytes,
        mime_type: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> GenerationResult:
        client = self._get_client()
        if self.provider == "openai":
            encoded_image = base64.b64encode(image_data).decode("ascii")
            request = {
                "model": self.model,
                "instructions": instructions,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "Transcribe the supplied image."},
                            {
                                "type": "input_image",
                                "image_url": f"data:{mime_type};base64,{encoded_image}",
                            },
                        ],
                    }
                ],
                "reasoning": {"effort": "none"},
            }
            if max_output_tokens is not None:
                request["max_output_tokens"] = max_output_tokens
            response = self._create_openai_response(**request)
            return self._openai_result(response, self.model)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            safety_settings=self._google_safety_settings(),
            http_options=(
                types.HttpOptions(timeout=self.timeout_minutes * 60_000)
                if self.timeout_minutes is not None
                else None
            ),
            system_instruction=[instructions],
        )
        response = client.models.generate_content(
            model=self.model,
            contents=[types.Part.from_bytes(data=image_data, mime_type=mime_type)],
            config=config,
        )
        usage = response.usage_metadata
        return GenerationResult(
            text=response.text or "",
            prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            model=self.model,
            provider="google",
            finish_reason=None,
        )
