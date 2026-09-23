"""Orchestration boundary for the AI provider.

The concrete NVIDIA/LLM implementation belongs to the AI-agent workstream.
This backend-facing boundary keeps the shared request/result contract stable.
"""

from __future__ import annotations

from typing import Protocol

from .contracts import AgentServices, AssistantRequest, AssistantResult, ProductHit


class AssistantHandler(Protocol):
    def handle_message(self, request: AssistantRequest, services: AgentServices) -> AssistantResult: ...


class UnconfiguredAssistant:
    """Explicit fallback until the NVIDIA-backed handler is configured."""

    def handle_message(self, request: AssistantRequest, services: AgentServices) -> AssistantResult:
        """Deterministic fallback with the same contract as the real agent."""
        products = services.catalog.search(request.text)
        hits = [
            ProductHit(
                product_id=product.id,
                score=1.0,
                reason="Совпадение по артикулу или названию",
                matched_attributes={},
            )
            for product in products
        ]
        answer = (
            f"Нашёл в тестовой выборке {len(hits)} товар(а)."
            if hits
            else "В тестовой выборке не нашёл подходящий товар. Попробуйте указать артикул или часть названия."
        )
        return AssistantResult(answer=answer, products=hits)
