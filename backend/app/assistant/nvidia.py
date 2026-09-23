"""OpenAI-compatible NVIDIA NIM client boundary.

The client is deliberately opt-in. Missing configuration keeps the local
deterministic MVP available and never causes a startup failure.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib import request as http_request


@dataclass(frozen=True)
class NvidiaConfig:
    base_url: str
    model: str
    api_key: str

    @classmethod
    def from_env(cls) -> "NvidiaConfig | None":
        model = os.getenv("NVIDIA_MODEL", "").strip()
        api_key = os.getenv("NVIDIA_API_KEY", "").strip()
        if not model or not api_key:
            return None
        return cls(
            base_url=os.getenv(
                "NVIDIA_BASE_URL",
                "https://integrate.api.nvidia.com/v1",
            ).rstrip("/"),
            model=model,
            api_key=api_key,
        )


class NvidiaClient:
    def __init__(self, config: NvidiaConfig, timeout_seconds: float = 20.0) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        payload = json.dumps(
            {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "stream": False,
            }
        ).encode("utf-8")
        http_request_object = http_request.Request(
            f"{self.config.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with http_request.urlopen(http_request_object, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        if isinstance(content, str):
            content = json.loads(content)
        if not isinstance(content, dict):
            raise ValueError("NVIDIA response is not a JSON object")
        return content
