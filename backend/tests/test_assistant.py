"""Acceptance tests for the five must-have scenarios of the ekt.kz case.

Run from the repository root:
    python -m pip install -r backend/requirements-dev.txt
    python -m pytest backend/tests -q

The LLM is disabled here so the tests are deterministic and need no API key.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.assistant.llm_client as llm_client

llm_client.NvidiaLLMClient.from_env = classmethod(lambda cls: None)

from app.main import app  # noqa: E402  (import after disabling the LLM)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def session(client: TestClient) -> str:
    return client.post("/api/v1/sessions").json()["session_id"]


def say(client: TestClient, session: str, text: str) -> dict:
    response = client.post(f"/api/v1/sessions/{session}/messages", json={"message": text})
    assert response.status_code == 200, response.text
    return response.json()


def cart_items(client: TestClient, session: str) -> list[dict]:
    return client.get(f"/api/v1/sessions/{session}/cart").json()["items"]


# 1. Availability, specs and certificate -------------------------------------------------

def test_stock_by_city_and_specs(client, session):
    body = say(client, session, "Есть 027228 в Алматы?")
    card = body["products"][0]
    assert card["id"] == 515291
    assert card["quantity"] == 5
    assert "64 920" in body["answer"]
    assert "Legrand" in body["answer"]


def test_conflicting_attribute_is_visible(client, session):
    body = say(client, session, "027228")
    assert any("Конфликт" in warning for warning in body["products"][0]["warnings"])
    assert "160 А / 250 А" in body["answer"]


def test_follow_up_city_uses_dialog_context(client, session):
    say(client, session, "027228")
    body = say(client, session, "а в Нур-Султане?")
    assert body["products"][0]["quantity"] == 8


def test_missing_certificate_is_not_invented(client, session):
    say(client, session, "027228")
    body = say(client, session, "покажи сертификат")
    assert "не приложен" in body["answer"]
    assert "ekt.kz" in body["answer"]


def test_unknown_stock_is_not_zero(client, session):
    body = say(client, session, "RM35BA10")
    assert body["products"][0]["quantity"] is None


# 2. Analogs for out-of-stock items ------------------------------------------------------

def test_out_of_stock_offers_explained_analog(client, session):
    body = say(client, session, "Нужен 027230")
    ids = [card["id"] for card in body["products"]]
    assert ids[0] == 515288 and body["products"][0]["quantity"] == 0
    assert 515291 in ids
    analog = next(card for card in body["products"] if card["id"] == 515291)
    assert analog["match_reason"].startswith("Аналог")
    assert "совпадает" in analog["match_reason"]


# 3. Purchase terms ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "question, expected",
    [
        ("Условия доставки и оплаты?", "Доставка"),
        ("минимальная партия?", "Минимальная партия"),
        ("Жеткізу қалай?", "Доставка"),
    ],
)
def test_purchase_terms(client, session, question, expected):
    body = say(client, session, question)
    assert expected in body["answer"]
    assert "демонстрационного магазина" in body["answer"]


# 4. Cart changes only after explicit confirmation, within stock -------------------------

def test_proposal_does_not_change_cart(client, session):
    say(client, session, "Есть 027228 в Алматы?")
    body = say(client, session, "добавь 2 штуки")
    assert body["pending_confirmation"]["items"][0]["quantity"] == 2
    assert cart_items(client, session) == []


def test_text_confirmation_adds_once(client, session):
    say(client, session, "Есть 027228 в Алматы?")
    say(client, session, "добавь 2 штуки")
    body = say(client, session, "да, добавь")
    assert body["cart"]["items"][0]["quantity"] == 2
    say(client, session, "да")
    assert cart_items(client, session)[0]["quantity"] == 2


def test_button_confirmation_is_idempotent(client, session):
    say(client, session, "Есть 027228 в Алматы?")
    confirmation = say(client, session, "добавь 1 шт")["pending_confirmation"]["confirmation_id"]
    url = f"/api/v1/sessions/{session}/confirmations/{confirmation}/confirm"
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 409
    assert cart_items(client, session)[0]["quantity"] == 1


def test_quantity_never_exceeds_stock(client, session):
    say(client, session, "Есть 027228 в Алматы?")
    say(client, session, "добавь 4 штуки")
    say(client, session, "да, добавь")
    body = say(client, session, "добавь 2 штуки")
    assert body["pending_confirmation"] is None
    assert "Добавить не получится" in body["answer"]
    assert cart_items(client, session)[0]["quantity"] == 4


def test_yes_without_proposal_changes_nothing(client, session):
    body = say(client, session, "да, добавь")
    assert body["cart"] is None
    assert cart_items(client, session) == []


def test_foreign_session_cannot_confirm(client, session):
    say(client, session, "Есть 027228 в Алматы?")
    confirmation = say(client, session, "добавь 1 шт")["pending_confirmation"]["confirmation_id"]
    other = client.post("/api/v1/sessions").json()["session_id"]
    response = client.post(f"/api/v1/sessions/{other}/confirmations/{confirmation}/confirm")
    assert response.status_code == 409
    assert cart_items(client, other) == []


def test_kazakh_add_and_confirm(client, session):
    say(client, session, "027228 Астанада бар ма?")
    assert say(client, session, "екеуін себетке қосыңызшы")["pending_confirmation"]
    body = say(client, session, "иә, қосыңыз")
    assert body["cart"]["items"][0]["quantity"] == 2


# 5. Link to the cart --------------------------------------------------------------------

def test_cart_link_after_adding(client, session):
    say(client, session, "Есть 027228 в Алматы?")
    say(client, session, "добавь 1 шт")
    body = say(client, session, "да")
    assert body["cart"]["cart_url"]


# LLM safety guard -----------------------------------------------------------------------

def test_llm_answer_with_changed_numbers_is_rejected():
    source = "Цена: 64 920 ₸. Наличие: 5 шт."
    assert llm_client._numbers_preserved(source, "Бағасы 64920 ₸, 5 дана бар")
    assert not llm_client._numbers_preserved(source, "Бағасы 999 ₸, 100 дана бар")
