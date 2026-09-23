"""Shared contracts between the backend, retrieval layer and AI agent.

These types intentionally keep product IDs as strings. The HTTP adapter may
serialize them as numbers for the frontend, but articles and IDs are never
used as numeric values while searching or loading data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol


MessageRole = Literal["user", "assistant", "system"]
FactStatus = Literal["verified", "unknown", "conflict"]
DataSource = Literal["snapshot", "synthetic"]


@dataclass
class Message:
    role: MessageRole
    content: str
    created_at: datetime


@dataclass
class AttachmentContent:
    attachment_id: str
    filename: str
    mime_type: str
    extracted_text: str | None = None
    image_description: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class CartItem:
    product_id: str
    quantity: int
    city: str | None = None
    location_id: str | None = None


@dataclass
class PendingConfirmation:
    confirmation_id: str
    items: list[CartItem]
    expires_at: datetime


@dataclass
class AttributeValue:
    value: str | list[str] | None
    status: FactStatus
    sources: list[str] = field(default_factory=list)


@dataclass
class Product:
    id: str
    article: str | None
    name: str
    category: str | None = None
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    attributes: dict[str, AttributeValue] = field(default_factory=dict)
    image_url: str | None = None
    product_url: str | None = None
    certificates: list[str] = field(default_factory=list)
    data_source: DataSource = "snapshot"


@dataclass
class SearchFilters:
    category: str | None = None
    city: str | None = None
    availability_only: bool = False
    max_price: Decimal | None = None
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class StockLocation:
    location_id: str
    location_name: str
    quantity: int


@dataclass
class StockInfo:
    product_id: str
    available_quantity: int | None
    locations: list[StockLocation] = field(default_factory=list)
    city: str | None = None
    checked_at: datetime | None = None
    source: DataSource = "snapshot"


@dataclass
class FAQEntry:
    id: str
    title: str
    content: str
    url: str | None = None
    updated_at: datetime | None = None


@dataclass
class Clarification:
    question: str
    missing_fields: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)


class CatalogRepository(Protocol):
    def find_by_id(self, product_id: str) -> Product | None: ...
    def search(self, query: str, filters: SearchFilters | None = None) -> list[Product]: ...


class InventoryRepository(Protocol):
    def get_stock(self, product_id: str, city: str | None = None) -> StockInfo: ...


class FAQRepository(Protocol):
    def search(self, query: str) -> list[FAQEntry]: ...
