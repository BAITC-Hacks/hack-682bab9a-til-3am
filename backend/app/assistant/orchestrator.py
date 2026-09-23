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
from .llm_client import NvidiaLLMClient
from .analogs import find_analogs, wants_analog


class AssistantHandler(Protocol):
    def handle_message(self, request: AssistantRequest, services: AgentServices) -> AssistantResult: ...


def handle_message(request: AssistantRequest, services: AgentServices) -> AssistantResult:
    """Process one message using read-only backend services.

    Deterministic baseline: facts (price, stock, specs) always come from the
    catalog; the optional NVIDIA adapter only helps to parse the request.
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

    if _is_certificate_question(text):
        return _certificate_answer(request, services, text)

    if _is_faq_question(text):
        entries = services.faq.search(text)
        if entries:
            parts = [entry.content for entry in entries]
            product = _context_product(request, services, text)
            if product is not None and any(entry.id == "min_order" for entry in entries):
                kratnost = product.attributes.get("KRATNOST_MIN")
                if kratnost and kratnost.value:
                    parts.append(f"Для «{product.name}» в карточке указана кратность: {kratnost.value} шт.")
                else:
                    parts.append(f"Для «{product.name}» кратность в данных не указана.")
            from app.faq import DEMO_LABEL  # local import avoids a package import cycle

            return AssistantResult(
                answer=f"{DEMO_LABEL}:\n\n" + "\n\n".join(parts) + "\n\nТочные условия для вашего заказа подтвердит менеджер.",
                products=[],
                evidence=[Evidence("faq", entry.id, entry.content, "verified") for entry in entries],
                action=None,
            )
        return AssistantResult(
            answer="В базе пока нет точных условий по этому вопросу. Уточните их у менеджера EKT.",
            products=[],
            evidence=[Evidence("faq", "search", text, "unknown")],
            action=None,
        )

    parsed = _parse_with_nvidia(text)
    effective_city = request.city or _extract_city(text) or (parsed.city if parsed else None) or _history_city(request)
    search_text = parsed.article if parsed and parsed.article else text
    filters = SearchFilters(city=effective_city)
    hits = _search_with_context(request, services, filters, search_text)
    if not hits:
        return AssistantResult(
            answer="Не нашёл товар по этому запросу. Укажите артикул или название (например, 027228, «автомат 160А» или «реле RM17»).",
            products=[],
            evidence=[Evidence("catalog", "search", text, "unknown")],
            clarification=Clarification(
                "Уточните артикул или название товара.", ["product"], []
            ),
            action=None,
        )

    if len(hits) > 1 and hits[0].score < 0.95:
        return AssistantResult(
            answer=f"Нашёл несколько подходящих товаров ({min(len(hits), 5)}). Уточните, какой именно нужен — укажите артикул.",
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
    stock = services.inventory.get_stock(product.id, effective_city)
    evidence.extend(stock_evidence(stock))
    answer = _build_product_answer(product, stock, effective_city)

    products = [hit]
    out_of_stock = stock.available_quantity == 0
    if out_of_stock or wants_analog(text):
        all_products = getattr(services.catalog, "all_products", None)
        analogs = find_analogs(product, all_products() if all_products else [], services.inventory, effective_city)
        if analogs:
            lead = "Этого товара нет в наличии. " if out_of_stock else ""
            answer += f"\n\n{lead}Предлагаю аналоги (обоснование — в карточках):"
            for analog in analogs:
                analog_product = services.catalog.find_by_id(analog.product_id)
                if analog_product is not None:
                    answer += f"\n• {analog_product.name} — {_format_price(analog_product.price)}"
            products.extend(analogs)
        else:
            answer += "\n\nПодходящих аналогов с подтверждённым наличием в текущих данных нет — менеджер подберёт замену."
        if out_of_stock or not _wants_add(text):
            return AssistantResult(answer=answer, products=products, evidence=evidence, clarification=None, action=None)

    quantity = parsed.quantity if parsed and parsed.quantity is not None else _requested_quantity(text)
    wants_add = _wants_add(text)
    action = None
    clarification = None
    if wants_add or quantity is not None:
        if quantity is None:
            clarification = Clarification(
                "Сколько единиц добавить?", ["quantity"], []
            )
            answer += "\n\nСколько штук добавить в корзину?"
        elif stock.available_quantity is None:
            clarification = Clarification(
                "В текущих данных нет подтверждённого остатка. Уточнить наличие?",
                ["stock"],
                [],
            )
            answer += "\n\nДобавить не могу: остаток не подтверждён. Уточните наличие у менеджера."
        elif quantity > stock.available_quantity:
            clarification = Clarification(
                f"Доступно только {stock.available_quantity} шт. Указать другое количество?",
                ["quantity"],
                [str(stock.available_quantity)],
            )
            answer += f"\n\nЗапрошено {quantity} шт., а доступно только {stock.available_quantity} шт. Укажите другое количество."
        else:
            action = ActionProposal(
                type="add_to_cart",
                items=[CartItem(product_id=product.id, quantity=quantity, city=effective_city)],
            )
            total = product.price * quantity if product.price is not None else None
            answer += (
                f"\n\nПодготовил добавление: {quantity} шт."
                + (f" на сумму {_format_price(total)}" if total is not None else "")
                + ". Корзина изменится только после вашего подтверждения — нажмите «Да, добавить»."
            )

    return AssistantResult(
        answer=answer,
        products=products,
        evidence=evidence,
        clarification=clarification,
        action=action,
    )


_KEY_ATTRIBUTES = (
    "OBYEM",
    "KOLICHESTVO_POLYUSOV",
    "NOMINALNYY_TOK",
    "NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST",
    "NOMINALNOE_NAPRYAZHENIE",
    "TIP_USTANOVKI",
    "TORGOVAYA_MARKA",
    "ARTIKULPOSTAVSHCHIKA",
)

_CITIES = {
    "алмат": "Алматы",
    "астан": "Нур-Султан",
    "нур-султан": "Нур-Султан",
    "нурсултан": "Нур-Султан",
    "шымкент": "Шымкент",
    "тараз": "Тараз",
    "атырау": "Атырау",
    "караганд": "Караганда",
    "актау": "Актау",
    "талдыкорган": "Талдыкорган",
    "усть-каменогорск": "Усть-Каменогорск",
}


def _extract_city(text: str) -> str | None:
    lowered = text.casefold()
    return next((city for token, city in _CITIES.items() if token in lowered), None)


def _history_city(request: AssistantRequest) -> str | None:
    for message in reversed(request.history):
        if message.role == "user" and message.content.strip() != request.text.strip():
            city = _extract_city(message.content)
            if city:
                return city
    return None


def _context_product(request: AssistantRequest, services: AgentServices, text: str):
    hits = search_products(services.catalog, text, SearchFilters())
    if not hits:
        for message in reversed(request.history):
            if message.role != "user" or message.content.strip() == text:
                continue
            hits = search_products(services.catalog, message.content, SearchFilters())
            if hits:
                break
    if not hits or (len(hits) > 1 and hits[0].score < 0.95):
        return None
    return services.catalog.find_by_id(hits[0].product_id)


def _is_certificate_question(text: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in ("сертификат", "декларац", "паспорт изделия", "ст-кз", "ст кз"))


def _certificate_answer(request: AssistantRequest, services: AgentServices, text: str) -> AssistantResult:
    product = _context_product(request, services, text)
    if product is None:
        return AssistantResult(
            answer="Укажите артикул товара, для которого нужен сертификат.",
            clarification=Clarification("Для какого товара нужен сертификат?", ["product"], []),
        )
    hit = ProductHit(product.id, 1.0, "Товар из запроса", {})
    if product.certificates:
        links = "\n".join(f"• {link}" for link in product.certificates)
        return AssistantResult(answer=f"Сертификаты для «{product.name}»:\n{links}", products=[hit])
    link = f"\nКарточка товара: {product.product_url}" if product.product_url else ""
    return AssistantResult(
        answer=(
            f"Для «{product.name}» файл сертификата в данных каталога не приложен, поэтому не могу его показать."
            f"{link}\nМенеджер пришлёт сертификат соответствия по запросу."
        ),
        products=[hit],
        evidence=[Evidence("catalog", "certificates", None, "unknown")],
    )


def _format_price(value) -> str:
    if value is None:
        return "цена не указана"
    return f"{int(value):,}".replace(",", " ") + " ₸"


def _build_product_answer(product, stock, city: str | None) -> str:
    from app.catalog import ATTRIBUTE_LABELS  # local import avoids a package import cycle

    lines = [product.name, f"Артикул: {product.article or 'не указан'} · Цена: {_format_price(product.price)}"]
    if stock.available_quantity is None:
        lines.append("Наличие: остаток не указан в доступных данных — уточните у менеджера.")
    else:
        where = f" в городе {city}" if city else ""
        demo = " (синтетический остаток демо)" if stock.source == "synthetic" else " (по выгрузке каталога)"
        lines.append(f"Наличие{where}: {stock.available_quantity} шт.{demo}")
        in_stock = [location for location in stock.locations if location.quantity > 0]
        if in_stock and not city:
            lines.append("По складам: " + ", ".join(f"{location.location_name} — {location.quantity}" for location in in_stock))
    specs = []
    for key in _KEY_ATTRIBUTES:
        attribute = product.attributes.get(key)
        if attribute is None or attribute.value in (None, ""):
            continue
        label = ATTRIBUTE_LABELS.get(key, key)
        if attribute.status == "conflict" and isinstance(attribute.value, list):
            specs.append(f"{label}: ⚠ данные расходятся ({' / '.join(attribute.value)}) — уточните у менеджера")
        else:
            specs.append(f"{label}: {attribute.value}")
    if specs:
        lines.append("Характеристики: " + "; ".join(specs))
    else:
        lines.append("Подробные характеристики в выгрузке отсутствуют — см. карточку на сайте.")
    return "\n".join(lines)


def _search_with_context(
    request: AssistantRequest,
    services: AgentServices,
    filters: SearchFilters,
    search_text: str | None = None,
) -> list[ProductHit]:
    """Search the current message, then recover the last discussed product.

    Follow-up messages such as ``Мне нужно 2 штуки`` intentionally contain no
    article. The backend supplies the bounded history, so the agent can safely
    resolve that reference without inventing a product.
    """
    current = (search_text or request.text).strip()
    hits = search_products(services.catalog, current, filters)
    if hits:
        return hits

    for message in reversed(request.history):
        content = message.content.strip()
        if not content or content == current or message.role != "user":
            continue
        hits = search_products(services.catalog, content, filters)
        if hits and _can_use_history(current):
            return hits
    return []


def _can_use_history(text: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in ("добав", "корзин", "налич", "остат", "сколько", "количеств", "аналог", "замен", "похож", "характерист", "цена", "стоит", "шт")) or _extract_city(text) is not None


def _is_faq_question(text: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in ("оплат", "достав", "гарант", "самовывоз", "минимальн", "партия", "партию", "кратност", "возврат", "условия покупки", "условия заказа"))


def _parse_with_nvidia(text: str):
    client = NvidiaLLMClient.from_env()
    return client.parse_request(text) if client is not None else None


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
    match = re.fullmatch(r"\s*(\d{1,3})\s*", lowered)
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
