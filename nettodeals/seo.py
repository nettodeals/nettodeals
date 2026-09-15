"""Small SEO helpers without external runtime dependencies."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime


def slugify(value: str, *, maximum: int = 90) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug[:maximum].rstrip("-") or "angebot"


def deal_path(deal_id: int, title: str) -> str:
    return f"/deal/{deal_id}/{slugify(title)}"


def display_datetime(value: str | None) -> str:
    if not value:
        return "nicht angegeben"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "nicht angegeben"
    return parsed.strftime("%d.%m.%Y, %H:%M Uhr")
