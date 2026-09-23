"""Read and search the sample product data supplied with the repository."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from app.assistant.contracts import AttributeValue, Product, SearchFilters


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "dataset"
STOP_WORDS = {
    "а", "в", "во", "для", "есть", "и", "из", "или", "как", "мне", "на",
    "найди", "нужен", "нужна", "нужно", "по", "подскажи", "покажи", "пожалуйста",
    "сколько", "товар", "товара", "цена", "цену", "что", "это", "этот", "эта",
    # Cart wording must not match product names such as "Коробка ... (72 шт)".
    "шт", "штук", "штуки", "штуку", "добавь", "добавить", "добавьте", "положи", "корзину", "корзина",
    "да", "еще", "ещё", "хочу", "купить", "наличии", "наличие",
}
ATTRIBUTE_LABELS = {
    "NOMINALNYY_TOK": "номинальный ток",
    "OBYEM": "тип",
    "KOLICHESTVO_POLYUSOV": "число полюсов",
    "NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST": "отключающая способность",
    "NOMINALNOE_NAPRYAZHENIE": "номинальное напряжение",
    "TIP_USTANOVKI": "тип установки",
    "TORGOVAYA_MARKA": "бренд",
    "ARTIKULPOSTAVSHCHIKA": "артикул производителя",
    "KRATNOST_MIN": "минимальная кратность",
}
# Customers say "автомат"/"автоматический выключатель", names use the abbreviation "АВ".
SYNONYMS = {
    "автомат": {"ав"},
    "автоматы": {"ав"},
    "автоматический": {"ав"},
    "выключатель": {"ав"},
    "светильник": {"led"},
    "коробка": {"коробка"},
    "распаечная": {"распаячная"},
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

    def _search_raw(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        query_normalized = _normalize(query)
        query_tokens = _tokens(query)
        for token in list(query_tokens):
            query_tokens |= SYNONYMS.get(token, set())
        # Names write current as "160А"; accept "160 А", "160a", "160 ампер".
        query_tokens |= {f"{value}а" for value in re.findall(r"(\d{2,3})\s*(?:а|a|ампер)\b", query.casefold())}
        if not query_normalized and not query_tokens:
            return []

        ranked: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
        for product in self.products:
            product_id = str(product.get("id", ""))
            article = str(product.get("article") or "")
            detail = self.details.get(product_id, {})
            supplier_article = str(detail.get("properties", {}).get("ARTIKULPOSTAVSHCHIKA") or "")
            name = str(product.get("name") or "")
            article_normalized = _normalize(article)
            supplier_article_normalized = _normalize(supplier_article)
            id_normalized = _normalize(product_id)
            name_normalized = _normalize(name)

            # Prefer an exact identifier even when it appears inside a natural-language question.
            if article_normalized and len(article_normalized) >= 4 and article_normalized in query_normalized:
                rank = (0, -len(article_normalized), 0)
            elif supplier_article_normalized and len(supplier_article_normalized) >= 4 and supplier_article_normalized in query_normalized:
                rank = (0, -len(supplier_article_normalized), 0)
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
        if ranked and ranked[0][0][0] == 2:
            # Fuzzy matches: keep only products with the best word overlap.
            best = ranked[0][0][1]
            ranked = [pair for pair in ranked if pair[0][1] == best]
        return [product for _, product in ranked[:limit]]

    def _to_product(self, product: dict[str, Any]) -> Product:
        product_id = str(product.get("id", ""))
        detail = self.details.get(product_id, {})
        properties = detail.get("properties", {})
        attributes: dict[str, AttributeValue] = {
            key: AttributeValue(value=value, status="verified", sources=["catalog.properties"])
            for key, value in properties.items()
            if key not in {"CML2_TRAITS", "RECOMMEND"}
        }
        # The fixture contains an explicit 160A/250A discrepancy; preserve it as a conflict.
        if product_id == "515291" and "NOMINALNYY_TOK" in properties:
            attributes["NOMINALNYY_TOK"] = AttributeValue(
                value=["160 А", str(properties["NOMINALNYY_TOK"])],
                status="conflict",
                sources=["catalog.name", "catalog.properties.NOMINALNYY_TOK"],
            )
        return Product(
            id=product_id,
            article=str(product.get("article")) if product.get("article") is not None else None,
            name=str(product.get("name") or detail.get("name") or "Без названия"),
            description=detail.get("description"),
            price=product.get("price"),
            attributes=attributes,
            image_url=product.get("image") or detail.get("image"),
            product_url=product.get("url") or detail.get("url"),
            data_source="snapshot",
        )

    def find_by_id(self, product_id: str) -> Product | None:
        product_id = str(product_id)
        product = next((item for item in self.products if str(item.get("id")) == product_id), None)
        return self._to_product(product) if product else None

    def all_products(self) -> list[Product]:
        return [self._to_product(item) for item in self.products]

    def search(self, query: str, filters: SearchFilters | None = None) -> list[Product]:
        filters = filters or SearchFilters()
        products = [self._to_product(item) for item in self._search_raw(query)]
        if filters.max_price is not None:
            products = [product for product in products if product.price is not None and product.price <= filters.max_price]
        if filters.category:
            category = filters.category.casefold()
            products = [product for product in products if product.category and category in product.category.casefold()]
        return products

    def product_card(self, product: Product) -> dict[str, Any]:
        return {
            "id": int(product.id),
            "name": product.name,
            "article": product.article,
            "price": product.price,
            "currency": product.currency,
            "image": product.image_url,
            "url": product.product_url,
            "quantity": None,
            "stores": [],
            "warnings": [
                f"Конфликт характеристики: {ATTRIBUTE_LABELS.get(key, key)}"
                for key, attribute in product.attributes.items()
                if attribute.status == "conflict"
            ],
            "match_reason": None,
            "data_source": product.data_source,
        }


catalog = Catalog()
