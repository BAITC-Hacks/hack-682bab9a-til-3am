from __future__ import annotations

from typing import Protocol

from .contracts import (
    ActionProposal,
    AgentServices,
    AssistantRequest,
    AssistantResult,
    CartItem,
    Clarification,
    Evidence,
    ProductHit,
    SearchFilters,
)
from .retrieval import product_evidence, search_products, stock_evidence


class AssistantHandler(Protocol):
    def handle_message(self, request: AssistantRequest, services: AgentServices) -> AssistantResult: ...


def handle_message(request: AssistantRequest, services: AgentServices) -> AssistantResult:
    """Process one message using read-only backend services.

    This deterministic MVP intentionally does not call the cart or an LLM. It
    provides a safe baseline that can later be augmented by an NVIDIA adapter.
    """
    text = request.text.strip()
    if not text:
        return AssistantResult(
            answer="Напишите, какой товар вас интересует.",
            products=[],
            evidence=[],
            clarification=Clarification("Какой товар найти?", ["query"], []),
            action=None,
        )

    filters = SearchFilters(city=request.city)
    hits = _search_with_context(request, services, filters)
    if not hits:
        return AssistantResult(
            answer="Не нашёл товар по этому запросу. Укажите артикул или название.",
            products=[],
            evidence=[Evidence("catalog", "search", text, "unknown")],
            clarification=Clarification(
                "Уточните артикул или название товара.", ["product"], []
            ),
            action=None,
        )

    if len(hits) > 1 and hits[0].score < 0.95:
        return AssistantResult(
            answer="Нашёл несколько похожих товаров. Уточните, какой именно нужен.",
            products=hits[:5],
            evidence=[],
            clarification=Clarification(
                "Какой товар выбрать?", ["product"], [hit.product_id for hit in hits[:5]]
            ),
            action=None,
        )

    hit = hits[0]
    product = services.catalog.find_by_id(hit.product_id)
    if product is None:
        return AssistantResult(
            answer="Товар найден, но его подробная карточка сейчас недоступна.",
            products=[hit],
            evidence=[Evidence("catalog", "product", hit.product_id, "unknown")],
            clarification=None,
            action=None,
        )

    evidence = product_evidence(product)
    stock = services.inventory.get_stock(product.id, request.city)
    evidence.extend(stock_evidence(stock))
    answer = _build_product_answer(product.name, stock.available_quantity, request.city)

    quantity = _requested_quantity(text)
    wants_add = _wants_add(text)
    action = None
    clarification = None
    if wants_add or quantity is not None:
        if quantity is None:
            clarification = Clarification(
                "Сколько единиц добавить?", ["quantity"], []
            )
        elif stock.available_quantity is None:
            clarification = Clarification(
                "В текущих данных нет подтверждённого остатка. Уточнить наличие?",
                ["stock"],
                [],
            )
        elif quantity > stock.available_quantity:
            clarification = Clarification(
                f"Доступно только {stock.available_quantity} шт. Указать другое количество?",
                ["quantity"],
                [str(stock.available_quantity)],
            )
        else:
            action = ActionProposal(
                type="add_to_cart",
                items=[CartItem(product_id=product.id, quantity=quantity, city=request.city)],
            )
            answer += f" Подготовил предложение добавить {quantity} шт. в корзину."

    return AssistantResult(
        answer=answer,
        products=[hit],
        evidence=evidence,
        clarification=clarification,
        action=action,
    )


def _build_product_answer(name: str, quantity: int | None, city: str | None) -> str:
    location = f" в городе {city}" if city else ""
    if quantity is None:
        availability = "Остаток не указан в доступных данных."
    else:
        availability = f"Доступно: {quantity} шт."
    return f"Товар: {name}. {availability}{location}"


def _search_with_context(request: AssistantRequest, services: AgentServices, filters: SearchFilters) -> list[ProductHit]:
    """Search the current message, then recover the last discussed product.

    Follow-up messages such as ``Мне нужно 2 штуки`` intentionally contain no
    article. The backend supplies the bounded history, so the agent can safely
    resolve that reference without inventing a product.
    """
    current = request.text.strip()
    hits = search_products(services.catalog, current, filters)
    if hits:
        return hits

    for message in reversed(request.history):
        content = message.content.strip()
        if not content or content == current or message.role != "user":
            continue
        hits = search_products(services.catalog, content, filters)
        if hits:
            return hits
    return []


def _requested_quantity(text: str) -> int | None:
    import re

    lowered = text.casefold()
    # A bare number may be an article (for example, 027228), so only treat
    # numbers as quantities when the wording gives us a quantity signal.
    patterns = (
        r"\b(\d{1,3})\s*(?:шт|штук|штуки|единиц|товар(?:а|ов)?)\b",
        r"\b(?:нужно|нужн(?:а|о)|количество|добавь|положи|возьми)\s+(\d{1,3})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1))
    # PowerShell clients can mangle Cyrillic text in the request body. A short
    # standalone number is still safe to treat as a quantity here; long
    # numeric articles such as 027228 are deliberately excluded.
    match = re.search(r"\b(\d{1,3})\b", lowered)
    if match:
        return int(match.group(1))
    return None


def _wants_add(text: str) -> bool:
    lowered = text.casefold()
    return any(word in lowered for word in ("добавь", "добавить", "положи", "в корзину"))


class UnconfiguredAssistant:
    """Adapter preserving the backend handler interface for the MVP function."""

    def handle_message(self, request: AssistantRequest, services: AgentServices) -> AssistantResult:
        return handle_message(request, services)
