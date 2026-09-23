"""Read and search the sample product data supplied with the repository."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "json"
STOP_WORDS = {
    "а", "в", "во", "для", "есть", "и", "из", "или", "как", "мне", "на",
    "найди", "нужен", "нужна", "нужно", "по", "подскажи", "покажи", "пожалуйста",
    "сколько", "товар", "товара", "цена", "цену", "что", "это", "этот", "эта",
}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in value if character.isalnum())


def _tokens(value: str) -> set[str]:
    tokens = re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold())
    return {token for token in tokens if token not in STOP_WORDS and len(token) > 1}


class Catalog:
    """Small in-memory catalog adapter for the local demo fixtures."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        self.products: list[dict[str, Any]] = []
        self.details: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        products_by_id: dict[str, dict[str, Any]] = {}
        for filename in ("api_products.json", "api_products_page2.json"):
            page = _read_json(self.data_dir / filename)
            for item in page.get("items", []):
                product_id = str(item.get("id", ""))
                if product_id:
                    products_by_id[product_id] = {**item, "id": product_id}

        detail = _read_json(self.data_dir / "api_products_detail.json")
        detail_id = str(detail.get("id", ""))
        self.details = {detail_id: detail} if detail_id else {}
        self.products = list(products_by_id.values())

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        query_normalized = _normalize(query)
        query_tokens = _tokens(query)
        if not query_normalized and not query_tokens:
            return []

        ranked: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
        for product in self.products:
            product_id = str(product.get("id", ""))
            article = str(product.get("article") or "")
            name = str(product.get("name") or "")
            article_normalized = _normalize(article)
            id_normalized = _normalize(product_id)
            name_normalized = _normalize(name)

            # Prefer an exact identifier even when it appears inside a natural-language question.
            if article_normalized and len(article_normalized) >= 4 and article_normalized in query_normalized:
                rank = (0, -len(article_normalized), 0)
            elif id_normalized and len(id_normalized) >= 4 and id_normalized in query_normalized:
                rank = (0, -len(id_normalized), 0)
            elif name_normalized and name_normalized in query_normalized:
                rank = (1, -len(name_normalized), 0)
            else:
                product_tokens = _tokens(f"{name} {article} {product_id}")
                overlap = len(query_tokens & product_tokens)
                if overlap == 0:
                    continue
                # Higher overlap first; shorter queries win ties to avoid noisy partial matches.
                rank = (2, -overlap, len(query_tokens))

            ranked.append((rank, product))

        ranked.sort(key=lambda pair: pair[0])
        return [product for _, product in ranked[:limit]]

    def product_card(self, product: dict[str, Any]) -> dict[str, Any]:
        product_id = str(product.get("id", ""))
        return {
            "id": product_id,
            "name": product.get("name", "Без названия"),
            "article": product.get("article"),
            "price": product.get("price"),
            "image": product.get("image"),
            "url": product.get("url"),
            "has_details": product_id in self.details,
        }


catalog = Catalog()
