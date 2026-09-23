from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except ImportError:  # Keep the deterministic MVP usable without optional config support.
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ParsedRequest:
    intent: str | None = None
    article: str | None = None
    quantity: int | None = None
    city: str | None = None


class NvidiaLLMClient:
    """Small OpenAI-compatible NVIDIA NIM client with a bounded timeout."""

    def __init__(self, base_url: str, model: str, api_key: str, timeout: float = 8.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> NvidiaLLMClient | None:
        base_url = os.getenv("NVIDIA_BASE_URL")
        model = os.getenv("NVIDIA_MODEL")
        api_key = os.getenv("NVIDIA_API_KEY")
        if not base_url or not model or not api_key:
            return None
        return cls(base_url, model, api_key)

    def parse_request(self, text: str) -> ParsedRequest | None:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Разбери запрос покупателя. Верни только JSON без markdown "
                        "с полями intent, article, quantity, city. "
                        "Если значение неизвестно, используй null. quantity — целое число."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_tokens": 256,
            "stream": False,
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            data = _parse_json_object(content)
            return ParsedRequest(
                intent=_optional_string(data.get("intent")),
                article=_optional_string(data.get("article")),
                quantity=_optional_quantity(data.get("quantity")),
                city=_optional_string(data.get("city")),
            )
        except HTTPError as exc:
            logger.warning("NVIDIA request failed with HTTP %s", exc.code)
            return None
        except URLError as exc:
            logger.warning("NVIDIA connection failed: %s", exc.reason)
            return None
        except (TimeoutError, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("NVIDIA response could not be parsed (%s)", type(exc).__name__)
            return None


def _parse_json_object(content: str) -> dict[str, object]:
    if not isinstance(content, str):
        raise ValueError("NVIDIA response content is not text")
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("NVIDIA response is not a JSON object")
    return value


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_quantity(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        quantity = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return quantity if quantity is not None and 0 < quantity <= 100000 else None
