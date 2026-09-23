"""Explainable analog search over the local catalog.

Features are parsed from product names (the only field present for every
item). Candidates must share the product type; the reason lists what matches,
what differs and what is unknown, so a recommendation is never presented as
guaranteed compatibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .contracts import InventoryRepository, Product, ProductHit


@dataclass
class Features:
    kind: str | None
    series: str | None
    current: str | None
    breaking: str | None
    poles: str | None
    brand: str | None
    voltage: str | None


_KINDS = (
    ("ав", "автоматический выключатель"),
    ("диф", "дифавтомат"),
    ("реле", "реле контроля"),
    ("коробка", "коробка"),
    ("led", "светильник"),
    ("il mx", "светильник"),
)
_BRANDS = ("legrand", "megalight", "opple", "schneider", "stark")


def features(name: str) -> Features:
    lowered = name.casefold()
    kind = next((label for token, label in _KINDS if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", lowered) or token in lowered.split()), None)
    if kind is None and "реле" in lowered:
        kind = "реле контроля"
    series = re.search(r"\b(drx\s?\d+|rm\d{2}[a-z]*|уп[а-я]*)", lowered)
    current = re.search(r"(\d{1,4})\s*[аa](?![-\w])", lowered)
    breaking = re.search(r"(\d{1,3})\s*k[аa]", lowered.replace("к", "k"))
    poles = re.search(r"(\d)\s*[фp]\b|(\d)p\+n", lowered)
    voltage = re.search(r"(\d+\s*[…\.-]+\s*\d+\s*v)", lowered)
    brand = next((brand for brand in _BRANDS if brand in lowered), None)
    series_value = series.group(1).replace(" ", "") if series else None
    if series_value and series_value.startswith("rm"):
        series_value = series_value[:4]
    return Features(
        kind=kind,
        series=series_value,
        current=current.group(1) if current else None,
        breaking=breaking.group(1) if breaking else None,
        poles=(poles.group(1) or poles.group(2)) if poles else None,
        brand=brand,
        voltage=voltage.group(1).replace(" ", "") if voltage else None,
    )


_LABELS = {
    "series": ("серия", ""),
    "current": ("номинальный ток", " А"),
    "breaking": ("отключающая способность", " кА"),
    "poles": ("полюсов", ""),
    "brand": ("бренд", ""),
    "voltage": ("диапазон", ""),
}
_WEIGHTS = {"current": 4, "voltage": 4, "series": 2, "poles": 2, "breaking": 1, "brand": 1}


def find_analogs(
    source: Product,
    candidates: list[Product],
    inventory: InventoryRepository,
    city: str | None = None,
    limit: int = 3,
) -> list[ProductHit]:
    base = features(source.name)
    if base.kind is None:
        return []
    scored: list[tuple[float, ProductHit]] = []
    for candidate in candidates:
        if candidate.id == source.id:
            continue
        other = features(candidate.name)
        if other.kind != base.kind:
            continue
        stock = inventory.get_stock(candidate.id, city)
        if not stock.available_quantity:
            continue
        score = 0.0
        same: list[str] = []
        diff: list[str] = []
        for field, weight in _WEIGHTS.items():
            left, right = getattr(base, field), getattr(other, field)
            if left is None and right is None:
                continue
            label, unit = _LABELS[field]
            if left == right:
                score += weight
                same.append(f"{label} {right}{unit}")
            else:
                diff.append(f"{label}: {right or '—'}{unit if right else ''} вместо {left or '—'}{unit if left else ''}")
        # A different current rating is a different product class for breakers; heavily penalise it.
        if base.current and other.current and base.current != other.current:
            score -= 3
        if score <= 0:
            continue
        stock_note = f"в наличии {stock.available_quantity} шт." + (" (синтетический остаток демо)" if stock.source == "synthetic" else "")
        reason = "Аналог: тот же тип — " + base.kind
        if same:
            reason += "; совпадает: " + ", ".join(same)
        if diff:
            reason += "; отличается: " + "; ".join(diff)
        reason += f"; {stock_note}. Совместимость с вашей схемой проверьте по паспорту изделия."
        scored.append((score, ProductHit(candidate.id, min(score / 14, 0.94), reason, {})))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [hit for _, hit in scored[:limit]]


def wants_analog(text: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in ("аналог", "замен", "похож", "вместо", "альтернатив"))
