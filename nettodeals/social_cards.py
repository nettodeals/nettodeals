"""Locally rendered text cards; no third-party photos, fonts, or AI service."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = Path(__file__).resolve().parent / "assets" / "DejaVuSans.ttf"


def _font(size: int):
    return ImageFont.truetype(str(FONT_PATH), size=size)


def _wrap(draw, text: str, font, width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        proposed = f"{current} {word}".strip()
        if draw.textlength(proposed, font=font) <= width:
            current = proposed
            continue
        if current:
            lines.append(current)
            current = ""
        for char in word:
            if current and draw.textlength(current + char, font=font) > width:
                lines.append(current)
                current = ""
            current += char
    if current:
        lines.append(current)
    return lines


def render_card(title: str, category: str, source_date: str, portrait: bool = False) -> bytes:
    height = 1920 if portrait else 1350
    image = Image.new("RGB", (1080, height), "#f5f6fc")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / height
        draw.line((0, y, 1080, y), fill=(int(244 + 5 * ratio), int(247 - 3 * ratio), 253))
    top = 180 if portrait else 85
    draw.rounded_rectangle((55, top, 1025, height - top), radius=45, fill="white")
    draw.rounded_rectangle((105, top + 65, 370, top + 78), radius=6, fill="#7064bf")
    small = _font(28)
    medium = _font(34)
    draw.text((105, top + 120), "PRODUKT-STECKBRIEF", font=small, fill="#675692")
    draw.text((105, top + 175), "Schweizer Einkaufsradar", font=medium, fill="#596478")
    font = _font(58)
    lines = _wrap(draw, title[:300], font, 850)
    while len(lines) > 7 and font.size > 30:
        font = _font(font.size - 2)
        lines = _wrap(draw, title[:300], font, 850)
    y = top + 275
    for line in lines:
        draw.text((105, y), line, font=font, fill="#202a40")
        y += int(font.size * 1.25)
    y = max(y + 45, height - top - 320)
    for line in _wrap(draw, category[:80], medium, 850):
        draw.text((105, y), line, font=medium, fill="#676084")
        y += 44
    draw.text((105, height - top - 160), f"Quellenstand: {source_date}", font=small, fill="#626c7c")
    draw.text((105, height - top - 100), "Kein bestätigter Rabatt. Kein eigener Test.", font=small, fill="#626c7c")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
