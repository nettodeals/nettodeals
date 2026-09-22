"""One editorial editor for imported links, reviewed deals and social exports."""
import hashlib
import json
import re
from io import BytesIO
from typing import Annotated
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

import requests
from fastapi import Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from .db import connection, now_iso, upsert_deal
from .editorial import _youtube_reviews, is_direct_merchant_url, publish_deal
from .merchant import fetch_public, parse_product
from .security import csrf_token, normalize_external_url
from .services import DealCandidate, safe_money
from .studio import digest, gemini_copy, package_texts, product_image, render_deal_card


def register_studio_routes(app, settings, render, session_cookie, verify_csrf):
    def load(deal_id):
        with connection(settings.db_path) as conn:
            row = conn.execute('SELECT * FROM deals WHERE id=?', (deal_id,)).fetchone()
            pack = conn.execute('SELECT * FROM studio_packages WHERE deal_id=?', (deal_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Deal nicht gefunden')
        return dict(row), dict(pack) if pack else None

    def page(request, deal_id, message='', error=''):
        cookie = session_cookie(request, settings)
        deal, pack = load(deal_id)
        texts = json.loads(pack['texts']) if pack else package_texts(deal, settings)
        stale = bool(pack and pack['fingerprint'] != digest(deal))
        with connection(settings.db_path) as conn:
            count = conn.execute('SELECT count(*) FROM studio_attempts WHERE created_at>=?', (now_iso()[:10],)).fetchone()[0]
        return render('studio.html', deal=deal, pack=pack, texts=texts, stale=stale,
                      message=message, error=error, gemini=bool(settings.gemini_api_key),
                      model=settings.gemini_model, used=count, csrf_token=csrf_token(settings.admin_token, cookie))

    @app.post('/admin/merchant/import')
    def merchant_import(request: Request, csrf: Annotated[str, Form()], url: Annotated[str, Form()]):
        verify_csrf(request, settings, csrf)
        url = normalize_external_url(url)
        if not is_direct_merchant_url(url):
            raise HTTPException(422, 'Bitte einen direkten HTTPS-Händlerlink angeben.')
        sid = hashlib.sha256(url.encode()).hexdigest()
        with connection(settings.db_path) as conn:
            existing = conn.execute("SELECT id FROM deals WHERE source='merchant' AND source_id=?", (sid,)).fetchone()
        if existing:
            return RedirectResponse(f"/admin/studio/{existing['id']}", 303)
        try:
            raw, final_url = fetch_public(url)
            if not is_direct_merchant_url(final_url):
                raise ValueError('Weiterleitung führt nicht zu einem Händlerangebot.')
            data = parse_product(raw, final_url)
        except ValueError as exc:
            data = dict(title='Händlerangebot prüfen', shop_name=urlsplit(url).hostname,
                        base_price=0, image_url='', description='', affiliate_link=url, notes=str(exc))
        candidate = DealCandidate(title=data['title'], category='Deals', shop_name=data['shop_name'],
            affiliate_link=data['affiliate_link'], base_price=data['base_price'],
            description=data['description'], image_url=data['image_url'], image_source=url,
            source='merchant', source_id=sid, source_url=url, link_type='editorial')
        upsert_deal(settings.db_path, candidate.values(status='draft'))
        with connection(settings.db_path) as conn:
            row = conn.execute("SELECT id FROM deals WHERE source='merchant' AND source_id=?", (sid,)).fetchone()
            conn.execute('UPDATE deals SET enrichment_notes=? WHERE id=?', (data['notes'], row['id']))
        return RedirectResponse(f"/admin/studio/{row['id']}", 303)

    @app.get('/admin/studio/{deal_id}')
    def studio_page(request: Request, deal_id: int):
        return page(request, deal_id)

    @app.post('/admin/studio/{deal_id}/prepare')
    def prepare(request: Request, deal_id: int, csrf: Annotated[str, Form()],
                title: Annotated[str, Form()], shop_name: Annotated[str, Form()],
                affiliate_link: Annotated[str, Form()], base_price: Annotated[float, Form()],
                facts: Annotated[str, Form()] = '', image_url: Annotated[str, Form()] = '',
                image_source: Annotated[str, Form()] = '', rights: Annotated[str, Form()] = 'no',
                checked: Annotated[str, Form()] = 'no', use_gemini: Annotated[str, Form()] = 'no',
                reference_price: Annotated[float, Form()] = 0,
                reference_kind: Annotated[str, Form()] = 'none', reference_source: Annotated[str, Form()] = ''):
        verify_csrf(request, settings, csrf)
        deal, _ = load(deal_id)
        if deal['status'] != 'draft':
            return page(request, deal_id, error='Nur Entwürfe lassen sich vorbereiten. Veröffentlichte Deals zuerst beenden und neu prüfen.')
        link = normalize_external_url(affiliate_link)
        source = normalize_external_url(reference_source)
        if not title.strip() or not shop_name.strip() or not is_direct_merchant_url(link):
            return page(request, deal_id, error='Titel, Händlername und direkter HTTPS-Link fehlen.')
        if reference_kind not in ('none', 'merchant', 'uvp') or (reference_kind != 'none' and safe_money(reference_price) > 0 and not source):
            return page(request, deal_id, error='Vergleichsart und belegende HTTPS-Quelle prüfen.')
        timestamp = now_iso()
        with connection(settings.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            queued = conn.execute('SELECT status FROM deal_queue WHERE deal_id=?', (deal_id,)).fetchone()
            if queued and queued['status'] == 'processing':
                raise HTTPException(409, 'Deal wird gerade veröffentlicht.')
            conn.execute('DELETE FROM deal_queue WHERE deal_id=?', (deal_id,))
            conn.execute('DELETE FROM ai_drafts WHERE deal_id=?', (deal_id,))
            conn.execute('''UPDATE deals SET title=?, shop_name=?, affiliate_link=?, base_price=?, effective_price=?,
                coupon_discount=0, payment_bonus=0, description=?, image_url=?, image_source=?, image_rights_confirmed=?,
                manufacturer_uvp=?, uvp_source_url=?, comparison_price=?, comparison_source=?,
                price_checked_at=?, updated_at=?, review_summary='', price_type='exact' WHERE id=?''',
                (title.strip()[:300], shop_name.strip()[:120], link, safe_money(base_price), safe_money(base_price),
                 facts[:3000], normalize_external_url(image_url), image_source[:2048], int(rights == 'yes'),
                 safe_money(reference_price) if reference_kind == 'uvp' else 0, source if reference_kind == 'uvp' else '',
                 safe_money(reference_price) if reference_kind == 'merchant' else 0, source if reference_kind == 'merchant' else '',
                 timestamp if checked == 'yes' else None, timestamp, deal_id))
        deal, _ = load(deal_id)
        snapshot = digest(deal)
        notes, copy, provider = [], None, 'Textvorlage'
        if use_gemini == 'yes':
            try:
                copy = gemini_copy(settings, deal)
                provider = settings.gemini_model
            except ValueError as exc:
                notes.append(str(exc))
        texts = package_texts(deal, settings, copy)
        feed, story = None, None
        if rights == 'yes' and deal['image_url'] and deal['image_source']:
            try:
                photo = product_image(deal['image_url'])
                feed = render_deal_card(deal, photo)
                story = render_deal_card(deal, photo, portrait=True)
            except ValueError as exc:
                notes.append(str(exc))
        else:
            notes.append('Für Produktgrafiken Bildquelle und Nutzungsrecht für Website und Social Media bestätigen.')
        with connection(settings.db_path) as conn:
            current = dict(conn.execute('SELECT * FROM deals WHERE id=?', (deal_id,)).fetchone())
            if digest(current) != snapshot or current['status'] != 'draft':
                raise HTTPException(409, 'Daten wurden inzwischen geändert; bitte neu vorbereiten.')
            conn.execute('''INSERT INTO studio_packages(deal_id,fingerprint,texts,provider,notes,feed,story,created_at,approved)
                VALUES (?,?,?,?,?,?,?,?,0) ON CONFLICT(deal_id) DO UPDATE SET fingerprint=excluded.fingerprint,
                texts=excluded.texts,provider=excluded.provider,notes=excluded.notes,feed=excluded.feed,
                story=excluded.story,created_at=excluded.created_at,approved=0''',
                (deal_id, snapshot, json.dumps(texts, ensure_ascii=False), provider, ' '.join(notes), feed, story, timestamp))
        return page(request, deal_id, message='Deal- und Social-Entwürfe vorbereitet. Texte prüfen und freigeben.')

    @app.post('/admin/studio/{deal_id}/approve')
    def approve(request: Request, deal_id: int, csrf: Annotated[str, Form()], expected: Annotated[str, Form()],
                summary: Annotated[str, Form()], x: Annotated[str, Form()], instagram: Annotated[str, Form()],
                tiktok: Annotated[str, Form()], script: Annotated[str, Form()], confirmed: Annotated[str, Form()] = 'no'):
        verify_csrf(request, settings, csrf)
        deal, pack = load(deal_id)
        if not pack or expected != digest(deal) or pack['fingerprint'] != expected or deal['status'] != 'draft':
            raise HTTPException(409, 'Entwurf veraltet; neu vorbereiten.')
        if confirmed != 'yes':
            return page(request, deal_id, error='Bitte Texte und Fakten prüfen und bestätigen.')
        texts = dict(summary=summary, x=x, instagram=instagram, tiktok=tiktok, script=script)
        x_weight = len(re.sub(r'https?://\S+', 'x' * 23, x))
        if x_weight > 280:
            raise HTTPException(422, 'X-Text zu lang: maximal 280 Zeichen inklusive verkürzter Links.')
        if any(len(v) > 5000 or not v.strip() for v in texts.values()):
            raise HTTPException(422, 'Texte müssen ausgefüllt und maximal 5000 Zeichen lang sein.')
        with connection(settings.db_path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT * FROM deals WHERE id=?', (deal_id,)).fetchone()
            current_pack = conn.execute('SELECT * FROM studio_packages WHERE deal_id=?', (deal_id,)).fetchone()
            if not current or current['status'] != 'draft' or digest(dict(current)) != expected or not current_pack or current_pack['fingerprint'] != expected:
                raise HTTPException(409, 'Daten wurden inzwischen geändert; erneut prüfen.')
            conn.execute('UPDATE studio_packages SET texts=?,approved=1 WHERE deal_id=?', (json.dumps(texts, ensure_ascii=False), deal_id))
            conn.execute('UPDATE deals SET review_summary=? WHERE id=?', (summary, deal_id))
        return page(request, deal_id, message='Texte freigegeben. Deal jetzt veröffentlichen oder im Kontrollzentrum einplanen.')

    @app.post('/admin/studio/{deal_id}/publish')
    def publish(request: Request, deal_id: int, csrf: Annotated[str, Form()]):
        verify_csrf(request, settings, csrf)
        deal, pack = load(deal_id)
        if not pack or not pack['approved'] or pack['fingerprint'] != digest(deal):
            return page(request, deal_id, error='Zuerst aktuelle Texte freigeben.')
        try:
            publish_deal(settings.db_path, deal_id, settings)
        except ValueError as exc:
            return page(request, deal_id, error=str(exc))
        return page(request, deal_id, message='Deal veröffentlicht. Social-Beiträge kannst du jetzt manuell posten.')

    @app.get('/admin/studio/{deal_id}/image/{kind}')
    def card(request: Request, deal_id: int, kind: str):
        session_cookie(request, settings)
        deal, pack = load(deal_id)
        if kind not in ('feed', 'story') or not pack or not pack.get(kind):
            raise HTTPException(404, 'Grafik fehlt; Produktbild und Rechte prüfen.')
        if pack['fingerprint'] != digest(deal):
            raise HTTPException(409, 'Grafik veraltet; neu vorbereiten.')
        return Response(pack[kind], media_type='image/png', headers={'Cache-Control': 'no-store'})

    @app.get('/admin/studio/{deal_id}/download')
    def download(request: Request, deal_id: int):
        session_cookie(request, settings)
        deal, pack = load(deal_id)
        if not pack or pack['fingerprint'] != digest(deal):
            raise HTTPException(409, 'Paket fehlt oder ist veraltet; neu vorbereiten.')
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            for key, value in json.loads(pack['texts']).items():
                archive.writestr(key+'.txt', value)
            for kind in ('feed', 'story'):
                if pack[kind]:
                    archive.writestr(kind+'.png', pack[kind])
            archive.writestr('STATUS.txt', f"Dealstatus: {deal['status']}\nTexte freigegeben: {bool(pack['approved'])}\nVor dem Posten Preis und Veröffentlichung prüfen.\n{pack['notes']}")
        return Response(output.getvalue(), media_type='application/zip', headers={
            'Content-Disposition': f'attachment; filename="nettodeals-{deal_id}-social.zip"', 'Cache-Control': 'no-store'})

    @app.post('/admin/studio/{deal_id}/youtube')
    def youtube(request: Request, deal_id: int, csrf: Annotated[str, Form()]):
        verify_csrf(request, settings, csrf)
        deal, _ = load(deal_id)
        if not settings.youtube_api_key:
            return page(request, deal_id, error='Optional: YOUTUBE_API_KEY für YouTube Data API v3 hinterlegen.')
        try:
            videos = _youtube_reviews(deal['title'], settings)
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return page(request, deal_id, error='YouTube-Suche fehlgeschlagen; Deal bleibt unverändert.')
        with connection(settings.db_path) as conn:
            conn.execute('UPDATE deals SET youtube_reviews=? WHERE id=?', (json.dumps(videos), deal_id))
        return page(request, deal_id, message=f'{len(videos)} YouTube-Suchtreffer gespeichert. Modellzuordnung prüfen.')
