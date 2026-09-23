"""Cart boundary owned by backend.

The AI agent never calls this adapter directly. It can only propose CartItem
values; the HTTP layer creates and confirms a one-time confirmation token.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.assistant.contracts import CartItem, InventoryRepository, PendingConfirmation
from app.catalog import Catalog


@dataclass
class CartResult:
    session_id: str
    items: list[CartItem] = field(default_factory=list)
    cart_url: str | None = None


class CartError(ValueError):
    pass


class MockCartAdapter:
    def __init__(self, catalog: Catalog, inventory: InventoryRepository) -> None:
        self.catalog = catalog
        self.inventory = inventory
        self._pending: dict[tuple[str, str], PendingConfirmation] = {}
        self._carts: dict[str, dict[str, CartItem]] = {}

    def create_confirmation(self, session_id: str, items: list[CartItem]) -> PendingConfirmation:
        if not items:
            raise CartError("Корзина не может быть пустой")
        checked: list[CartItem] = []
        for item in items:
            if item.quantity <= 0:
                raise CartError("Количество должно быть положительным")
            if self.catalog.find_by_id(item.product_id) is None:
                raise CartError(f"Товар {item.product_id} не найден")
            stock = self.inventory.get_stock(item.product_id, item.city)
            if stock.available_quantity is None or item.quantity > stock.available_quantity:
                raise CartError(f"Недостаточно остатка для товара {item.product_id}")
            checked.append(item)

        confirmation = PendingConfirmation(
            confirmation_id=str(uuid4()),
            items=checked,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        self._pending[(session_id, confirmation.confirmation_id)] = confirmation
        return confirmation

    def confirm(self, session_id: str, confirmation_id: str) -> CartResult:
        key = (session_id, confirmation_id)
        confirmation = self._pending.pop(key, None)
        if confirmation is None:
            raise CartError("Подтверждение не найдено или уже использовано")
        if confirmation.expires_at <= datetime.now(timezone.utc):
            raise CartError("Срок подтверждения истёк")

        # Re-check stock immediately before mutating the cart.
        for item in confirmation.items:
            stock = self.inventory.get_stock(item.product_id, item.city)
            if stock.available_quantity is None or item.quantity > stock.available_quantity:
                raise CartError(f"Остаток изменился для товара {item.product_id}")

        cart = self._carts.setdefault(session_id, {})
        for item in confirmation.items:
            existing = cart.get(item.product_id)
            quantity = (existing.quantity if existing else 0) + item.quantity
            cart[item.product_id] = CartItem(
                product_id=item.product_id,
                quantity=quantity,
                city=item.city,
                location_id=item.location_id,
            )
        return self.get_cart(session_id)

    def get_cart(self, session_id: str) -> CartResult:
        return CartResult(
            session_id=session_id,
            items=list(self._carts.get(session_id, {}).values()),
            cart_url=f"http://localhost:5173/cart/{session_id}",
        )
