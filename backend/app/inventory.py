"""Inventory repository backed by the detailed local product fixture.

Products without a detail fixture fall back to a clearly labelled synthetic
overlay (``demo_data/stock_overrides.json``) so the out-of-stock -> analog
scenario can be demonstrated. Real snapshot stock is never overwritten.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.catalog import Catalog
from app.assistant.contracts import StockInfo, StockLocation

DEMO_STOCK_PATH = Path(__file__).resolve().parents[2] / "demo_data" / "stock_overrides.json"


def _load_overrides(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("products", {})


class FixtureInventoryRepository:
    def __init__(self, catalog: Catalog, overrides_path: Path = DEMO_STOCK_PATH) -> None:
        self.catalog = catalog
        self.overrides = _load_overrides(overrides_path)

    def get_stock(self, product_id: str, city: str | None = None) -> StockInfo:
        detail: dict[str, Any] | None = self.catalog.details.get(str(product_id))
        source = "snapshot"
        if detail is None:
            detail = self.overrides.get(str(product_id))
            source = "synthetic"
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
            wanted = city.casefold()
            locations = [location for location in locations if location.location_name.casefold().startswith(wanted)]
            quantity = sum(location.quantity for location in locations)
        else:
            locations = [location for location in locations if location.quantity > 0] or locations
            quantity = detail.get("quantity")
            if quantity is None:
                quantity = sum(location.quantity for location in locations)
        return StockInfo(
            product_id=str(product_id),
            available_quantity=int(quantity) if quantity is not None else None,
            locations=locations,
            city=city,
            checked_at=datetime.now(timezone.utc),
            source=source,
        )
