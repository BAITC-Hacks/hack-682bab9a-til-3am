"""HTTP API for the first local chat-assistant slice."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.catalog import catalog
from app.assistant.contracts import AgentServices, AssistantRequest, CartItem, Message
from app.assistant.orchestrator import AssistantHandler, UnconfiguredAssistant, resolve_city
from app.cart.adapter import CartError, MockCartAdapter
from app.faq import FixtureFAQRepository
from app.inventory import FixtureInventoryRepository

load_dotenv()


app = FastAPI(title="ekt.kz Chat Assistant API", version="0.1.0")
origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Prototype-only session state. Replace with the site's session mechanism or a shared store.
sessions: dict[str, list[str]] = {}
# Only the latest proposal per session may be confirmed by text; a new proposal replaces it.
latest_confirmation: dict[str, str] = {}
CONFIRM_RE = re.compile(
    r"^(да|ага|ок|окей|конечно|подтверждаю|добавь|добавьте|добавляй|иә|иа|қос)"
    r"([\s,!.-]*(да|добавь|добавьте|добавить|добавляй|подтверждаю|в корзину|пожалуйста|иә|қос))*[\s!.]*$"
)
inventory = FixtureInventoryRepository(catalog)
faq = FixtureFAQRepository()
assistant_handler: AssistantHandler = UnconfiguredAssistant()
agent_services = AgentServices(catalog=catalog, inventory=inventory, faq=faq)
cart = MockCartAdapter(catalog, inventory)


class CreateSessionResponse(BaseModel):
    session_id: str


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ProductCard(BaseModel):
    id: int
    name: str
    article: str | None = None
    price: int | float | None = None
    currency: str | None = None
    image: str | None = None
    url: str | None = None
    quantity: int | None = None
    stores: list[dict[str, str | int]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    match_reason: str | None = None
    data_source: str


class CartItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)
    city: str | None = None
    location_id: str | None = None


class PendingConfirmationResponse(BaseModel):
    confirmation_id: str
    items: list[CartItemRequest]
    expires_at: datetime


class ConfirmationResponse(BaseModel):
    confirmation_id: str
    items: list[CartItemRequest]
    expires_at: datetime


class CartResponse(BaseModel):
    session_id: str
    items: list[CartItemRequest]
    cart_url: str


class MessageResponse(BaseModel):
    answer: str
    products: list[ProductCard]
    pending_confirmation: PendingConfirmationResponse | None = None
    # Filled only when this message was an explicit text confirmation that changed the cart.
    cart: CartResponse | None = None


@app.get("/api/v1/health")
def health() -> dict[str, str | int]:
    return {"status": "ok", "products_loaded": len(catalog.products)}


@app.post("/api/v1/sessions", response_model=CreateSessionResponse)
def create_session() -> CreateSessionResponse:
    session_id = str(uuid4())
    sessions[session_id] = []
    return CreateSessionResponse(session_id=session_id)


@app.post(
    "/api/v1/sessions/{session_id}/messages",
    response_model=MessageResponse,
)
def send_message(session_id: str, request: MessageRequest) -> MessageResponse:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Введите вопрос о товаре")

    sessions[session_id].append(message)
    # Keep only a small in-memory context window; the first slice searches the current message.
    sessions[session_id] = sessions[session_id][-10:]

    if CONFIRM_RE.match(message.casefold()):
        return _confirm_by_text(session_id)

    assistant_request = AssistantRequest(
        text=message,
        history=[Message(role="user", content=item, created_at=datetime.now(timezone.utc)) for item in sessions[session_id]],
    )
    result = assistant_handler.handle_message(assistant_request, agent_services)
    city = resolve_city(assistant_request)
    answer = result.answer
    cards = []
    for hit in result.products:
        product = catalog.find_by_id(hit.product_id)
        if product is None:
            continue
        stock = agent_services.inventory.get_stock(product.id, city)
        card = catalog.product_card(product)
        card["match_reason"] = hit.reason
        card["quantity"] = stock.available_quantity
        if stock.source == "synthetic":
            card["data_source"] = "synthetic"
            card["warnings"].append("Остаток синтетический (демо-сценарий аналога), не данные ekt.kz")
        card["stores"] = [
            {
                "id": location.location_id,
                "name": location.location_name,
                "quantity": location.quantity,
            }
            for location in stock.locations
        ]
        cards.append(card)

    pending_confirmation = None
    if result.action is not None and result.action.type == "add_to_cart":
        try:
            confirmation = cart.create_confirmation(session_id, result.action.items)
            latest_confirmation[session_id] = confirmation.confirmation_id
            pending_confirmation = PendingConfirmationResponse(
                confirmation_id=confirmation.confirmation_id,
                items=[CartItemRequest(**item.__dict__) for item in confirmation.items],
                expires_at=confirmation.expires_at,
            )
        except CartError as error:
            # A stale or incomplete proposal must not mutate the cart or expose
            # a confirmation token. Replace the offer text with the reason.
            pending_confirmation = None
            answer = answer.split("\n\nПодготовил добавление")[0] + f"\n\nДобавить не получится: {str(error).rstrip('.')}. Укажите меньшее количество."

    return MessageResponse(
        answer=answer,
        products=cards,
        pending_confirmation=pending_confirmation,
    )


def _cart_response(result) -> CartResponse:
    return CartResponse(
        session_id=result.session_id,
        items=[CartItemRequest(**item.__dict__) for item in result.items],
        cart_url=result.cart_url or "",
    )


def _confirm_by_text(session_id: str) -> MessageResponse:
    """Explicit text confirmation ("да, добавь") uses the same server-side check as the button."""
    confirmation_id = latest_confirmation.pop(session_id, None)
    if confirmation_id is None:
        return MessageResponse(
            answer="Сейчас нет предложения, которое нужно подтвердить. Напишите, какой товар и сколько штук добавить.",
            products=[],
        )
    try:
        result = cart.confirm(session_id, confirmation_id)
    except CartError as error:
        return MessageResponse(
            answer=f"Не удалось добавить: {str(error).rstrip('.')}. Корзина не изменилась — запросите товар ещё раз.",
            products=[],
        )
    lines = []
    total = 0
    for item in result.items:
        product = catalog.find_by_id(item.product_id)
        name = product.name if product else f"Товар {item.product_id}"
        price = product.price if product and product.price is not None else None
        if price is not None:
            total += price * item.quantity
        lines.append(f"• {name} — {item.quantity} шт." + (f" ({item.city})" if item.city else ""))
    answer = "Готово, добавил в корзину. Сейчас в корзине:\n" + "\n".join(lines)
    if total:
        answer += f"\nИтого: {int(total):,} ₸".replace(",", " ")
    answer += "\nПерейдите к корзине по ссылке ниже, чтобы оформить заказ."
    return MessageResponse(answer=answer, products=[], cart=_cart_response(result))


@app.post(
    "/api/v1/sessions/{session_id}/confirmations",
    response_model=ConfirmationResponse,
)
def create_confirmation(session_id: str, request: list[CartItemRequest]) -> ConfirmationResponse:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    try:
        confirmation = cart.create_confirmation(
            session_id,
            [CartItem(**item.model_dump()) for item in request],
        )
    except CartError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    latest_confirmation[session_id] = confirmation.confirmation_id
    return ConfirmationResponse(
        confirmation_id=confirmation.confirmation_id,
        items=[CartItemRequest(**item.__dict__) for item in confirmation.items],
        expires_at=confirmation.expires_at,
    )


@app.post(
    "/api/v1/sessions/{session_id}/confirmations/{confirmation_id}/confirm",
    response_model=CartResponse,
)
def confirm_cart(session_id: str, confirmation_id: str) -> CartResponse:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    try:
        result = cart.confirm(session_id, confirmation_id)
    except CartError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if latest_confirmation.get(session_id) == confirmation_id:
        latest_confirmation.pop(session_id)
    return CartResponse(
        session_id=result.session_id,
        items=[CartItemRequest(**item.__dict__) for item in result.items],
        cart_url=result.cart_url or "",
    )


@app.get("/api/v1/sessions/{session_id}/cart", response_model=CartResponse)
def get_cart(session_id: str) -> CartResponse:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    result = cart.get_cart(session_id)
    return CartResponse(
        session_id=result.session_id,
        items=[CartItemRequest(**item.__dict__) for item in result.items],
        cart_url=result.cart_url or "",
    )
