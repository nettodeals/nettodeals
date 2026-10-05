"""Reusable Otto artwork and deterministic, editable social drafts."""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from .db import now_iso
from .social_cards import _font, _wrap

POSES = ("explain", "question", "advise", "warn", "attention", "celebrate")
GOALS = ("follow", "visit", "discuss", "save")
USP = "Schweizer Deals. Preis, Nutzen, Haken."
ASSETS = Path(__file__).parent / "static" / "otto"


def angle(deal):
    title = deal.get("title", "").casefold()
    default_hook = "Passt dieses Angebot zu dir?"
    for word, question in (("monitor", "Neuer Monitor: Was braucht dein Arbeitsplatz?"),
                           ("headphone", "Neue Kopfhörer: Was ist dir wichtig?"),
                           ("oled", "Neuer Fernseher: Passt er zu deinem Alltag?"),
                           ("notebook", "Neues Notebook: Was brauchst du wirklich?")):
        if word in title:
            default_hook = question
            break
    return {
        "hook": deal.get("social_hook") or default_hook,
        "audience": deal.get("social_audience") or "",
        "benefit": deal.get("social_benefit") or "",
        "caveat": deal.get("social_caveat") or "",
        "question": deal.get("social_question") or "Wofür würdest du es einsetzen?",
    }


def cta(deal):
    goal = deal.get("social_goal") or "follow"
    return {
        "follow": "Folge NettoDeals für Schweizer Deals mit Einordnung.",
        "visit": f"Preis und Shop prüfen: nettodeals.ch/d/{deal['id']}",
        "discuss": angle(deal)["question"],
        "save": "Speichere den Vergleich für deine Kaufentscheidung. Preis vor dem Kauf neu prüfen.",
    }.get(goal, "Folge NettoDeals für Schweizer Deals mit Einordnung.")


def build_texts(deal, settings, copy=None):
    from .studio import comparison
    a = angle(deal)
    price = f"CHF {deal['effective_price']:.2f}"
    ref, label = comparison(deal)
    saving = (f"CHF {ref-deal['effective_price']:.2f} unter {label} CHF {ref:.2f} "
              f"(rund {round((ref-deal['effective_price'])/ref*100)} %).") if ref else ""
    url = settings.site_url + f"/d/{deal['id']}"
    title = deal["title"]
    disclosure = "Werbung · Affiliate-Link." if deal["link_type"] == "affiliate" else "Redaktioneller Link ohne Affiliate-Provision."
    date = str(deal.get("price_checked_at") or now_iso())[:10]
    benefit = f"Das spricht dafür: {a['benefit']}" if a["benefit"] else "Produkteigenschaften mit deinem Bedarf abgleichen."
    caveat = f"Darauf achten: {a['caveat']}" if a["caveat"] else "Vor dem Kauf Variante, Lieferumfang und Versandkosten prüfen."
    audience = f"Für: {a['audience']}." if a["audience"] else ""
    body = "\n".join(x for x in (audience, benefit, caveat) if x)
    lead = copy or {}
    summary = lead.get("summary") or "\n".join(x for x in (title, audience, benefit, caveat) if x)
    footer = f"Stand: {date}. Preis/Verfügbarkeit können sich ändern. {disclosure}"
    # Use one primary CTA per channel; no made-up scarcity or review experience.
    x = (f"{a['hook'][:46]}\n{title[:40]}\n{price} bei {deal['shop_name'][:22]}.\n"
         f"{'Werbung · ' if deal['link_type'] == 'affiliate' else ''}Preisänderungen möglich.\n"
         f"{('Folge für Schweizer Deals.' if deal.get('social_goal','follow') == 'follow' else 'Angebot und Details:')}\n{url}")
    instagram = (f"{a['hook']}\n\n{title}\n{lead.get('instagram', '')[:300]}\n{body}\n\n"
                 f"{price} · Gefunden bei {deal['shop_name']}\n{saving}\n\n"
                 f"{cta(deal)}\nDetails: {url}\n{USP}\n\n{footer}\n#NettoDeals #DealsSchweiz")
    tiktok = (f"{a['hook']}\n{title}\n{lead.get('tiktok', '')[:200]}\n{body}\n\n"
              f"{price} bei {deal['shop_name']}. {saving}\n"
              f"{cta(deal)}\nAlle Details: nettodeals.ch/d/{deal['id']}\n{USP}\n"
              f"{footer}\n#NettoDeals #DealsSchweiz")
    # Three frames, no opening logo sequence. Voice text contains only confirmed facts.
    script = (f"0–3 s | {a['hook']}\n"
              f"3–10 s | {title}. {audience} {benefit}\n"
              f"10–16 s | {caveat}\n"
              f"16–22 s | {price} bei {deal['shop_name']}. {saving}\n"
              f"22–26 s | {cta(deal)} Details auf nettodeals.ch, Deal {deal['id']}.\n"
              "Timing ist ein Vorschlag; an Sprechtempo anpassen. Kein eigener Produkttest.")
    return {"summary": summary + "\nKein eigener Produkttest.", "x": x,
            "instagram": instagram, "tiktok": tiktok, "script": script}


def paste_otto(image, pose, box):
    pose = pose if pose in POSES else "explain"
    with Image.open(ASSETS / (pose + ".png")) as mascot:
        mascot = ImageOps.contain(mascot.convert("RGBA"), (box[2], box[3]))
        image.paste(mascot, (box[0], box[1]), mascot)


def text_box(draw, text, box, size=52, color="#172644"):
    """Fit text without clipping; input length bounded by the editor."""
    x, y, width, height = box
    while size > 14:
        font = _font(size)
        lines = _wrap(draw, text, font, width)
        if len(lines) * (size + 12) <= height:
            break
        size -= 2
    for index, line in enumerate(lines):
        draw.text((x, y + index * (size + 12)), line, font=font, fill=color)


def render_sequence(deal, photo):
    """Three portrait PNGs suitable for a TikTok photo post or a Reel edit."""
    from .studio import comparison
    a = angle(deal)
    ref, label = comparison(deal)
    result = []
    for slide in range(1, 4):
        canvas = Image.new("RGB", (1080, 1920), "#f7f8ff")
        gradient = Image.new("RGB", (108, 192))
        gradient.putdata([(int(239-12*x/108), int(244-21*y/192), 255) for y in range(192) for x in range(108)])
        canvas.paste(gradient.resize(canvas.size, Image.Resampling.BICUBIC))
        draw = ImageDraw.Draw(canvas)
        draw.text((80, 175), "NettoDeals  /  Otto ordnet ein", font=_font(32), fill="#6250ad")
        draw.text((80, 235), USP, font=_font(32), fill="#35425d")
        if slide == 1:
            text_box(draw, a["hook"], (80, 325, 850, 230), 76)
            draw.rounded_rectangle((80, 610, 920, 1220), radius=40, fill="white")
            product = ImageOps.contain(photo.convert("RGBA"), (780, 550))
            canvas.paste(product, (500-product.width//2, 915-product.height//2), product)
            text_box(draw, deal["title"], (80, 1260, 600, 220), 40)
            text_box(draw, "Preis + Einordnung →", (80, 1500, 570, 100), 36, "#6250ad")
            paste_otto(canvas, deal.get("otto_pose"), (700, 1290, 230, 270))
        elif slide == 2:
            text_box(draw, "Passt es zu deinem Bedarf?", (80, 325, 850, 180), 68)
            draw.rounded_rectangle((80, 565, 920, 935), radius=32, fill="#ffffff")
            text_box(draw, "DAS SPRICHT DAFÜR" if a["benefit"] else "DEIN BEDARF", (110, 595, 740, 70), 32, "#52609c")
            text_box(draw, a["benefit"] or "Welche Eigenschaften sind dir wichtig?", (110, 690, 740, 205), 48)
            draw.rounded_rectangle((80, 975, 920, 1335), radius=32, fill="#f6f0ff")
            text_box(draw, "DARAUF ACHTEN", (110, 1010, 740, 70), 32, "#6551c8")
            text_box(draw, a["caveat"] or "Variante, Lieferumfang und Versandkosten beim Shop prüfen.", (110, 1100, 740, 200), 46)
            text_box(draw, "Einordnung, kein eigener Produkttest.", (80, 1410, 570, 120), 32)
            paste_otto(canvas, "question", (700, 1350, 230, 270))
        else:
            text_box(draw, "Der Preis im Überblick", (80, 325, 850, 170), 68)
            text_box(draw, f"CHF {deal['effective_price']:.2f}", (80, 535, 840, 150), 108)
            text_box(draw, "Gefunden bei " + deal["shop_name"], (80, 710, 800, 150), 46)
            saving = (f"CHF {ref-deal['effective_price']:.2f} weniger\nals {label} CHF {ref:.2f}") if ref else "Ohne belegten Vergleichspreis wird kein Rabatt behauptet."
            text_box(draw, saving, (80, 905, 810, 180), 42, "#6250ad")
            text_box(draw, cta(deal), (80, 1160, 800, 160), 48)
            text_box(draw, f"nettodeals.ch/d/{deal['id']}", (80, 1390, 620, 90), 40)
            paste_otto(canvas, "attention", (710, 1350, 220, 260))
        date = str(deal.get("price_checked_at") or now_iso())[:10]
        footer = f"Stand: {date} · Preisänderungen möglich."
        if deal["link_type"] == "affiliate":
            footer += " Werbung / Affiliate."
        text_box(draw, footer, (80, 1640, 840, 100), 26)
        output = BytesIO()
        canvas.save(output, format="PNG")
        result.append(output.getvalue())
    return result
