"""HTTP API for the first local chat-assistant slice."""

from __future__ import annotations

import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.catalog import catalog
from app.inventory import FixtureInventoryRepository


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


class MessageResponse(BaseModel):
    answer: str
    products: list[ProductCard]
    pending_confirmation: None = None


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

    inventory = FixtureInventoryRepository(catalog)
    matches = catalog.search(message)
    cards = []
    for product in matches:
        stock = inventory.get_stock(product.id)
        card = catalog.product_card(product)
        card["quantity"] = stock.available_quantity
        card["stores"] = [
            {
                "id": location.location_id,
                "name": location.location_name,
                "quantity": location.quantity,
            }
            for location in stock.locations
        ]
        cards.append(card)
    if cards:
        answer = f"Нашёл в тестовой выборке {len(cards)} товар(а). Цены и остатки нужно сверять с ekt.kz."
    else:
        answer = "В тестовой выборке не нашёл подходящий товар. Попробуйте указать артикул или часть названия."

    return MessageResponse(answer=answer, products=cards)
