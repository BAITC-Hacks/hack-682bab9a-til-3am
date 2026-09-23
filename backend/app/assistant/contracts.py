from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

MessageRole = Literal["user", "assistant", "system"]
FactStatus = Literal["verified", "unknown", "conflict"]
AttachmentKind = Literal["pdf", "docx", "xlsx", "jpeg", "other"]


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
    kind: AttachmentKind
    extracted_text: str | None
    image_description: str | None
    warnings: list[str]


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
    sources: list[str]


@dataclass
class Product:
    id: str
    article: str | None
    name: str
    category: str | None
    description: str | None
    price: Decimal | None
    currency: str | None
    attributes: dict[str, AttributeValue]
    image_url: str | None
    product_url: str | None
    certificates: list[str]


@dataclass
class SearchFilters:
    category: str | None = None
    city: str | None = None
    availability_only: bool = False
    max_price: Decimal | None = None
    attributes: dict[str, str] | None = None


@dataclass
class StockLocation:
    location_id: str
    location_name: str
    quantity: int


@dataclass
class StockInfo:
    product_id: str
    available_quantity: int | None
    locations: list[StockLocation]
    city: str | None
    checked_at: datetime
    source: str


@dataclass
class FAQEntry:
    id: str
    title: str
    content: str
    url: str | None
    updated_at: datetime | None


@dataclass
class Clarification:
    question: str
    missing_fields: list[str]
    options: list[str]


@dataclass
class ProductHit:
    product_id: str
    score: float
    reason: str
    matched_attributes: dict[str, str]


@dataclass
class Evidence:
    source: str
    field: str
    value: str | None
    status: FactStatus


@dataclass
class ActionProposal:
    type: Literal["add_to_cart"]
    items: list[CartItem]


@dataclass
class AssistantRequest:
    text: str
    history: list[Message]
    selected_products: list[str]
    city: str | None
    pending_confirmation: PendingConfirmation | None
    attachments: list[AttachmentContent]


@dataclass
class AssistantResult:
    answer: str
    products: list[ProductHit]
    evidence: list[Evidence]
    clarification: Clarification | None
    action: ActionProposal | None


class CatalogRepository(Protocol):
    def find_by_id(self, product_id: str) -> Product | None: ...

    def search(self, query: str, filters: SearchFilters) -> list[Product]: ...


class InventoryRepository(Protocol):
    def get_stock(self, product_id: str, city: str | None) -> StockInfo: ...


class FAQRepository(Protocol):
    def search(self, query: str) -> list[FAQEntry]: ...


@dataclass
class AgentServices:
    catalog: CatalogRepository
    inventory: InventoryRepository
    faq: FAQRepository
