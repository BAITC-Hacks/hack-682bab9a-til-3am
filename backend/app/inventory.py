"""Inventory repository backed by the detailed local product fixture."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.catalog import Catalog
from app.assistant.contracts import StockInfo, StockLocation


class FixtureInventoryRepository:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def get_stock(self, product_id: str, city: str | None = None) -> StockInfo:
        detail: dict[str, Any] | None = self.catalog.details.get(str(product_id))
        if detail is None:
            return StockInfo(
                product_id=str(product_id),
                available_quantity=None,
                city=city,
                checked_at=datetime.now(timezone.utc),
                source="snapshot",
            )

        locations = [
            StockLocation(
                location_id=str(store.get("id", "")),
                location_name=str(store.get("name", "")),
                quantity=int(store.get("quantity") or 0),
            )
            for store in detail.get("stores", [])
        ]
        if city:
            locations = [location for location in locations if location.location_name.casefold() == city.casefold()]
        quantity = sum(location.quantity for location in locations) if locations else detail.get("quantity")
        return StockInfo(
            product_id=str(product_id),
            available_quantity=int(quantity) if quantity is not None else None,
            locations=locations,
            city=city,
            checked_at=datetime.now(timezone.utc),
            source="snapshot",
        )
