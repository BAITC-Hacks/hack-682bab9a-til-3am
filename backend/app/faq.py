"""FAQ repository boundary.

The supplied fixtures do not contain approved payment, delivery or minimum
order terms, so the local implementation intentionally returns no facts until
the partner provides an approved FAQ dataset.
"""

from __future__ import annotations

from app.assistant.contracts import FAQEntry


class FixtureFAQRepository:
    def __init__(self, entries: list[FAQEntry] | None = None) -> None:
        self.entries = entries or []

    def search(self, query: str) -> list[FAQEntry]:
        query_terms = {term.casefold() for term in query.split() if len(term) > 1}
        if not query_terms:
            return []
        return [
            entry
            for entry in self.entries
            if query_terms & {term.casefold() for term in f"{entry.title} {entry.content}".split()}
        ]
