"""Retrieval boundary used by the AI agent.

The agent receives compact ProductHit values from this module. Full product
cards, prices and stock are always resolved by the backend after retrieval.
"""

from __future__ import annotations

from app.catalog import Catalog
from app.assistant.contracts import ProductHit, SearchFilters


class RetrievalService:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def search(self, query: str, filters: SearchFilters | None = None) -> list[ProductHit]:
        products = self.catalog.search(query, filters)
        return [
            ProductHit(
                product_id=product.id,
                score=1.0,
                reason="Совпадение по артикулу или названию",
                matched_attributes={},
            )
            for product in products
        ]
