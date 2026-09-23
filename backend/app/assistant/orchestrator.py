"""Orchestration boundary for the AI provider.

The concrete NVIDIA/LLM implementation belongs to the AI-agent workstream.
This backend-facing boundary keeps the shared request/result contract stable.
"""

from __future__ import annotations

from typing import Protocol

from .contracts import AssistantRequest, AssistantResult


class AssistantHandler(Protocol):
    def handle_message(self, request: AssistantRequest) -> AssistantResult: ...


class UnconfiguredAssistant:
    """Explicit fallback until the NVIDIA-backed handler is configured."""

    def handle_message(self, request: AssistantRequest) -> AssistantResult:
        return AssistantResult(
            answer="ИИ-агент пока не настроен. Можно выполнить поиск по артикулу или названию.",
        )
