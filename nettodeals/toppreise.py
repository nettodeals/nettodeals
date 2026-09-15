"""Parse user-supplied Toppreise HTML snapshots into editorial drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from .services import DealCandidate, safe_money

TOP_PRODUCTS_URL = "https://www.toppreise.ch/topprodukte"
NEW_TOP_PRICES_URL = "https://www.toppreise.ch/neue-toppreise"
MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024
MAX_ITEMS_PER_SNAPSHOT = 100
MIN_TOP100_ITEMS = 50
MIN_NEW48_ITEMS = 10


class SnapshotError(ValueError):
    """Raised when an uploaded snapshot is not the requested Toppreise view."""


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    candidates: list[DealCandidate]
    skipped: int


class _ToppreiseHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set[str]]] = []
        self.cards: list[dict[str, Any]] = []
        self.card: dict[str, Any] | None = None
        self.card_depth: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "a" and "Plugin_Product" in classes and self.card is None:
            self.card = {
                "entity_id": values.get("data-entity-id") or "",
                "href": values.get("href") or "",
                "title": [],
                "shipping_price": [],
                "product_price": [],
            }
            self.card_depth = len(self.stack)
        self.stack.append((tag, classes))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.card is None or not data.strip():
            return
        ancestor_classes = set().union(*(classes for _, classes in self.stack))
        if "product-name" in ancestor_classes:
            self.card["title"].append(data)
        if "Plugin_Price" in ancestor_classes:
            if "shippingPrice" in ancestor_classes:
                self.card["shipping_price"].append(data)
            elif "productPrice" in ancestor_classes:
                self.card["product_price"].append(data)

    def handle_endtag(self, tag: str) -> None:
        matching = next(
            (index for index in range(len(self.stack) - 1, -1, -1) if self.stack[index][0] == tag),
            None,
        )
        if matching is None:
            return
        if tag == "a" and self.card is not None and matching == self.card_depth:
            self.cards.append(self.card)
            self.card = None
            self.card_depth = None
        del self.stack[matching:]


def _category_from_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2 or parts[0] != "preisvergleich":
        return "Produkte"
    category = re.sub(r"[-_]+", " ", unquote(parts[1])).strip()
    return category[:80] or "Produkte"


def _price(card: dict[str, Any]) -> float:
    raw = card["shipping_price"] or card["product_price"]
    return safe_money(" ".join(raw))


def _is_toppreise_product(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"toppreise.ch", "www.toppreise.ch"}
        and parsed.path.startswith("/preisvergleich/")
    )


def parse_snapshot(html: str, *, collection: str, minimum_items: int = 1) -> SnapshotResult:
    """Parse a top-products or new-48-hours browser snapshot."""
    if collection not in {"top100", "new48"}:
        raise ValueError("Unbekannte Toppreise-Auswahl.")
    parser = _ToppreiseHTMLParser()
    parser.feed(html)
    candidates: list[DealCandidate] = []
    seen: set[str] = set()
    skipped = 0
    for card in parser.cards:
        if len(candidates) >= MAX_ITEMS_PER_SNAPSHOT:
            break
        entity_id = str(card["entity_id"]).strip()
        title = re.sub(r"\s+", " ", " ".join(card["title"])).strip()
        product_url = urljoin("https://www.toppreise.ch", str(card["href"]))
        price = _price(card)
        if not entity_id or entity_id in seen or not title or not price or not _is_toppreise_product(product_url):
            skipped += 1
            continue
        seen.add(entity_id)
        candidates.append(
            DealCandidate(
                title=title,
                category=_category_from_path(urlparse(product_url).path),
                base_price=price,
                shop_name="Preisvergleich",
                affiliate_link=product_url,
                source="toppreise",
                source_id=entity_id,
                description=(
                    "Redaktionelle Produktauswahl aus Top 100 beziehungsweise neuen "
                    "Toppreisen der letzten 48 Stunden auf Toppreise.ch. Keine Provision."
                ),
                source_url=product_url,
                link_type="editorial",
                source_name="Toppreise.ch",
                price_type="from",
            )
        )
    if not candidates:
        raise SnapshotError("In der HTML-Datei wurden keine Toppreise-Produkte erkannt.")
    if len(candidates) < minimum_items:
        raise SnapshotError(
            f"Es wurden nur {len(candidates)} Produkte erkannt; erwartet werden mindestens "
            f"{minimum_items}. Bitte Seite vollständig laden und erneut speichern."
        )
    return SnapshotResult(candidates=candidates, skipped=skipped)
