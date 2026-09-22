"""Editorial packages: optional Gemini copy, deterministic prices and local cards."""
import hashlib
import json
import re
from datetime import UTC, datetime
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from .ai_editor import FIELDS, PROMPT, validate_payload
from .db import connection, now_iso
from .merchant import fetch_public
from .seo import deal_path
from .social_cards import _font, _wrap


def digest(deal):
    fields = ('title', 'description', 'shop_name', 'affiliate_link', 'effective_price',
              'manufacturer_uvp', 'uvp_source_url', 'comparison_price', 'comparison_source',
              'image_url', 'image_source', 'image_rights_confirmed', 'price_checked_at', 'link_type')
    return hashlib.sha256(json.dumps({k: deal.get(k) for k in fields}, sort_keys=True).encode()).hexdigest()


def comparison(deal):
    if deal.get('comparison_source') and deal.get('comparison_price', 0) > deal['effective_price'] > 0:
        return deal['comparison_price'], 'Händler-Vergleichspreis'
    if deal.get('uvp_source_url') and deal.get('manufacturer_uvp', 0) > deal['effective_price'] > 0:
        return deal['manufacturer_uvp'], 'Hersteller-UVP'
    return 0, ''


def gemini_copy(settings, deal):
    if not settings.gemini_api_key:
        raise ValueError('Gemini nicht konfiguriert; Textvorlagen verwendet.')
    if not re.fullmatch(r'[a-zA-Z0-9.-]{1,80}', settings.gemini_model):
        raise ValueError('Ungültiger Gemini-Modellname; Textvorlagen verwendet.')
    with connection(settings.db_path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        count = conn.execute('SELECT count(*) FROM studio_attempts WHERE created_at>=?',
                             (datetime.now(UTC).date().isoformat(),)).fetchone()[0]
        if count >= 10:
            raise ValueError('Gemini-Pilotlimit: 10 Aufrufe pro UTC-Tag; Textvorlagen verwendet.')
        conn.execute('INSERT INTO studio_attempts(created_at) VALUES (?)', (now_iso(),))
    schema = {'type': 'OBJECT', 'properties': {k: {'type': 'STRING'} for k in FIELDS}, 'required': list(FIELDS)}
    try:
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent',
            headers={'x-goog-api-key': settings.gemini_api_key},
            json={'systemInstruction': {'parts': [{'text': PROMPT}]},
                  'contents': [{'role': 'user', 'parts': [{'text': json.dumps({'produkt': deal['title'], 'quellenmaterial': deal.get('description', '')[:3000]}, ensure_ascii=False)}]}],
                  'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': schema,
                                       'maxOutputTokens': 1800, 'temperature': 0.2}},
            timeout=(5, 35), allow_redirects=False)
        if response.status_code != 200:
            raise ValueError(f'Gemini HTTP {response.status_code}; Textvorlagen verwendet. API-Projekt, Modell und Kontingent prüfen.')
        candidate = response.json()['candidates'][0]
        if candidate.get('finishReason') != 'STOP':
            raise ValueError('Gemini-Antwort unvollständig; Textvorlagen verwendet.')
        raw = ''.join(p.get('text', '') for p in candidate['content']['parts'] if not p.get('thought'))
        return validate_payload(json.loads(raw))
    except (requests.RequestException, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Gemini nicht erreichbar oder Antwort unlesbar; Textvorlagen verwendet.') from exc


def package_texts(deal, settings, copy=None):
    price = f"CHF {deal['effective_price']:.2f}"
    ref, label = comparison(deal)
    saving = f"CHF {ref-deal['effective_price']:.2f} weniger als {label} CHF {ref:.2f} (rund {round((ref-deal['effective_price'])/ref*100)} %)." if ref else ''
    title = deal['title']
    url = settings.site_url + deal_path(deal['id'], title)
    date = str(deal.get('price_checked_at') or now_iso())[:10]
    disclosure = 'Affiliate-Link: Beim Kauf können wir eine Provision erhalten.' if deal['link_type'] == 'affiliate' else 'Redaktioneller Link ohne Affiliate-Provision.'
    footer = f'Stand: {date}. Preis und Verfügbarkeit können sich ändern. {disclosure}'
    lead = copy or {k: title for k in FIELDS}
    # X deliberately uses bounded plain text plus a URL counted as 23 characters by X.
    x = f"{title[:65]}\n{price} bei {deal['shop_name'][:30]}.\n"
    if ref:
        x += f"CHF {ref-deal['effective_price']:.2f} unter {label}.\n"
    x += ('Werbung · ' if deal['link_type'] == 'affiliate' else '') + 'Preisänderungen vorbehalten.\n' + url
    return {'summary': lead['summary'] + '\nKein eigener Produkttest.', 'x': x,
            'instagram': f"{lead['instagram']}\n\n{price} · Gefunden bei {deal['shop_name']}\n{saving}\n\nDetails: {url}\n\n{footer}\n#NettoDeals #DealsSchweiz",
            'tiktok': f"{lead['tiktok']}\n\n{price} bei {deal['shop_name']}. {saving}\nDetails auf nettodeals.ch, Suche nach {title}.\n\n{footer}\n#NettoDeals #DealsSchweiz",
            'script': f"{title} für {price} bei {deal['shop_name']}. {saving} Details auf nettodeals.ch. Aktuellen Preis vor dem Kauf prüfen."}


def product_image(url):
    raw, _ = fetch_public(url, limit=8_000_000)
    try:
        with Image.open(BytesIO(raw)) as original:
            if original.width * original.height > 20_000_000:
                raise ValueError('Produktbild zu gross.')
            original.load()
            return original.convert('RGBA')
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('Bilddatei nicht lesbar; PNG, JPEG oder WebP verwenden.') from exc


def render_deal_card(deal, photo, portrait=False):
    height = 1920 if portrait else 1350
    image = Image.new('RGB', (1080, height), '#f7f8ff')
    # Small deterministic gradient expanded smoothly: no remote image generation.
    gradient = Image.new('RGB', (108, 135))
    pixels = []
    for y in range(135):
        for x in range(108):
            blue = max(0, 1 - ((x-15)**2 + (y-35)**2)**0.5 / 65)
            pink = max(0, 1 - ((x-95)**2 + (y-100)**2)**0.5 / 75)
            pixels.append((int(247-35*blue+5*pink), int(248-25*blue-32*pink), int(255-5*pink)))
    gradient.putdata(pixels)
    image.paste(gradient.resize(image.size, Image.Resampling.BICUBIC))
    draw = ImageDraw.Draw(image)
    top = 180 if portrait else 55
    draw.text((65, top), 'NettoDeals', font=_font(52), fill='#142347', stroke_width=1)
    draw.rounded_rectangle((380,top+5,480,top+58),radius=24,fill='#e9e3ff')
    draw.text((400,top+13),'CH',font=_font(28),fill='#6551c8')
    title_font = _font(44)
    while len(_wrap(draw, deal['title'], title_font, 940)) > 3 and title_font.size > 22:
        title_font = _font(title_font.size-2)
    for i, line in enumerate(_wrap(draw, deal['title'], title_font, 940)[:3]):
        draw.text((65, top+90+i*(title_font.size+8)), line, font=title_font, fill='#142347')
    box_top = top + 275
    box_h = 660 if portrait else 440
    draw.rounded_rectangle((55,box_top-10,1025,box_top+box_h+10),radius=32,fill='white')
    thumb = ImageOps.contain(photo, (920, box_h))
    image.paste(thumb, ((1080-thumb.width)//2, box_top+(box_h-thumb.height)//2), thumb)
    y = box_top + box_h + 35
    price = f"CHF {deal['effective_price']:.2f}"
    font = _font(98)
    while draw.textlength(price, font=font) > 940:
        font = _font(font.size-2)
    draw.text((65, y), price, font=font, fill='#112248', stroke_width=2)
    ref, label = comparison(deal)
    y += 125
    if ref:
        draw.text((65, y), f'{label}: CHF {ref:.2f}', font=_font(30), fill='#526078')
        draw.rounded_rectangle((55,y+43,1025,y+101),radius=22,fill='#e6e3fc')
        draw.text((65, y+48), f"Rund -{round((ref-deal['effective_price'])/ref*100)} % | CHF {ref-deal['effective_price']:.2f} sparen", font=_font(38), fill='#6551c8')
    else:
        draw.text((65, y), 'Aktueller Angebotspreis', font=_font(30), fill='#526078')
    draw.text((65, y+110), 'Gefunden bei ' + deal['shop_name'][:35], font=_font(30), fill='#142347')
    footer_shift = 170 if portrait else 0
    draw.text((65, height-145-footer_shift), 'nettodeals.ch', font=_font(38), fill='#142347')
    draw.text((65, height-88-footer_shift), 'Stand: '+str(deal.get('price_checked_at') or now_iso())[:10], font=_font(23), fill='#526078')
    draw.text((65, height-52-footer_shift), 'Preis und Verfügbarkeit können sich ändern.', font=_font(23), fill='#526078')
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()
