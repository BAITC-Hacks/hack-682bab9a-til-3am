"""FAQ repository boundary.

The supplied fixtures do not contain approved payment, delivery or minimum
order terms. For the demo we load clearly labelled synthetic terms from
``demo_data/faq.json``; replace them with the partner's approved FAQ.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.assistant.contracts import FAQEntry

DEMO_FAQ_PATH = Path(__file__).resolve().parents[2] / "demo_data" / "faq.json"
DEMO_LABEL = "Условия демонстрационного магазина (допущение прототипа, не официальные правила ekt.kz)"


class FixtureFAQRepository:
    def __init__(self, entries: list[FAQEntry] | None = None, path: Path = DEMO_FAQ_PATH) -> None:
        self.keywords: dict[str, list[str]] = {}
        if entries is not None:
            self.entries = entries
            return
        self.entries = []
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for raw in data.get("entries", []):
                entry = FAQEntry(id=raw["id"], title=raw["title"], content=raw["content"])
                self.entries.append(entry)
                self.keywords[entry.id] = [keyword.casefold() for keyword in raw.get("keywords", [])]

    def search(self, query: str) -> list[FAQEntry]:
        lowered = query.casefold()
        return [
            entry
            for entry in self.entries
            if any(keyword in lowered for keyword in self.keywords.get(entry.id, []))
        ]

    def all_topics(self) -> list[FAQEntry]:
        return list(self.entries)
