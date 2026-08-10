import json
import logging
import re

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM provider is unavailable or returns an unusable response."""


class LLMService:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not configured; LLM features will fail until it is set")
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY or "not-set",
            base_url=settings.OPENAI_BASE_URL,
            timeout=30.0,
            max_retries=0,
        )

    def _ensure_configured(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise LLMError("OPENAI_API_KEY is not configured")

    async def generate(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.7, max_tokens: int = 2000
    ) -> str:
        self._ensure_configured()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = await self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            raise LLMError(f"LLM call failed: {e}") from e

        content = response.choices[0].message.content
        if not isinstance(content, str):
            raise LLMError("LLM returned an empty response")
        return content

    async def generate_json(self, prompt: str, *, system: str | None = None) -> dict[str, object]:
        self._ensure_configured()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "system",
                "content": "You are a helpful assistant that replies only with valid JSON. No markdown, no code fences.",
            }
        )
        messages.append({"role": "user", "content": prompt})
        try:
            response = await self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.error("LLM JSON call failed: %s", e)
            raise LLMError(f"LLM call failed: {e}") from e

        content = response.choices[0].message.content
        if not isinstance(content, str):
            raise LLMError("LLM returned an empty response")
        return _extract_json(content)


def _extract_json(content: str) -> dict[str, object]:
    """Parse JSON from LLM output, tolerating markdown fences and surrounding prose."""
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed: dict[str, object] = json.loads(text)
        return parsed
    except json.JSONDecodeError:
        pass

    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        try:
            parsed_obj: dict[str, object] = json.loads(obj_match.group(0))
            return parsed_obj
        except json.JSONDecodeError:
            pass

    arr_match = re.search(r"\[.*\]", text, re.DOTALL)
    if arr_match:
        try:
            return {"items": json.loads(arr_match.group(0))}
        except json.JSONDecodeError:
            pass

    raise LLMError("LLM response was not valid JSON")
