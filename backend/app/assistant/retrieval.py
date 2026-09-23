from __future__ import annotations

import re

from .contracts import (
    CatalogRepository,
    Evidence,
    Product,
    ProductHit,
    SearchFilters,
    StockInfo,
)

_ARTICLE_RE = re.compile(r"(?<![\w-])[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9_-]{2,}(?![\w-])")


def extract_query_candidates(text: str) -> list[str]:
    """Extract likely IDs/articles without treating them as facts."""
    return list(dict.fromkeys(_ARTICLE_RE.findall(text)))


def search_products(
    catalog: CatalogRepository,
    text: str,
    filters: SearchFilters,
) -> list[ProductHit]:
    candidates = extract_query_candidates(text)
    hits: list[ProductHit] = []

    for candidate in candidates:
        product = catalog.find_by_id(candidate)
        if product is not None:
            hits.append(
                ProductHit(
                    product_id=product.id,
                    score=1.0,
                    reason="Точное совпадение по идентификатору товара",
                    matched_attributes={"id": product.id},
                )
            )
            continue

        products = catalog.search(candidate, filters)
        for product in products:
            article = product.article or ""
            exact_article = article.casefold() == candidate.casefold()
            hits.append(
                ProductHit(
                    product_id=product.id,
                    score=0.95 if exact_article else 0.7,
                    reason=(
                        "Точное совпадение по артикулу"
                        if exact_article
                        else "Совпадение по названию или атрибутам"
                    ),
                    matched_attributes={"article": article} if exact_article else {},
                )
            )

    if not hits:
        for product in catalog.search(text, filters):
            hits.append(
                ProductHit(
                    product_id=product.id,
                    score=0.6,
                    reason="Совпадение по названию или атрибутам",
                    matched_attributes={},
                )
            )

    unique: dict[str, ProductHit] = {}
    for hit in hits:
        if hit.product_id not in unique or hit.score > unique[hit.product_id].score:
            unique[hit.product_id] = hit
    return sorted(unique.values(), key=lambda hit: hit.score, reverse=True)


def stock_evidence(stock: StockInfo) -> list[Evidence]:
    value = None if stock.available_quantity is None else str(stock.available_quantity)
    status = "unknown" if stock.available_quantity is None else "verified"
    return [Evidence(stock.source, "available_quantity", value, status)]


def product_evidence(product: Product) -> list[Evidence]:
    evidence = [Evidence("catalog", "name", product.name, "verified")]
    if product.article is None:
        evidence.append(Evidence("catalog", "article", None, "unknown"))
    else:
        evidence.append(Evidence("catalog", "article", product.article, "verified"))
    for field, attribute in product.attributes.items():
        evidence.append(
            Evidence(
                ",".join(attribute.sources) or "catalog",
                f"attributes.{field}",
                _attribute_text(attribute.value),
                attribute.status,
            )
        )
    return evidence


def _attribute_text(value: str | list[str] | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(value)
    return value
