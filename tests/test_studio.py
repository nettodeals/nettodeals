import json
from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from nettodeals.db import connection, init_db
from nettodeals.merchant import fetch_public, parse_product
from nettodeals.studio import gemini_copy
from tests.test_app import login
from tests.test_deal_workflow import draft

HTML = b'''<script type="application/ld+json">{"@type":"Product","name":"Monitor Example","description":"IPS panel","image":"/photo.png","offers":{"@type":"Offer","price":"55.00","priceCurrency":"CHF"}}</script>'''


def test_parse_offer_and_currency():
    data = parse_product(HTML, 'https://shop.example/product')
    assert data['base_price'] == 55 and data['image_url'] == 'https://shop.example/photo.png'
    assert parse_product(HTML.replace(b'CHF', b'EUR'), 'https://shop.example/p')['base_price'] == 0
    assert 'manufacturer_uvp' not in data


@pytest.mark.parametrize('ip', ['127.0.0.1', '10.0.0.1', '169.254.169.254', '::1', 'fc00::1', '224.0.0.1'])
def test_private_hosts_are_blocked(monkeypatch, ip):
    monkeypatch.setattr('nettodeals.merchant.socket.getaddrinfo', lambda *a, **k: [(2, 1, 6, '', (ip, 443))])
    with pytest.raises(ValueError):
        fetch_public('https://shop.example/p')


def test_merchant_import_draft_duplicate_and_auth(client, settings, monkeypatch):
    called = []
    def fetch(url):
        called.append(url)
        return HTML, url
    monkeypatch.setattr('nettodeals.studio_routes.fetch_public', fetch)
    assert client.post('/admin/merchant/import', data={'csrf':'bad','url':'https://shop.example/p'}).status_code == 401
    csrf = login(client, settings)
    for _ in range(2):
        response = client.post('/admin/merchant/import', data={'csrf':csrf,'url':'https://shop.example/p'})
        assert response.status_code == 200
        assert 'Monitor Example' in response.text
    assert len(called) == 1
    with connection(settings.db_path) as conn:
        rows = conn.execute('SELECT * FROM deals').fetchall()
        assert len(rows) == 1 and rows[0]['status'] == 'draft'
        assert not rows[0]['image_rights_confirmed']


def test_failed_import_remains_editable(client, settings, monkeypatch):
    def fail(url):
        raise ValueError('Händlerabruf HTTP 403. Angaben bitte manuell ergänzen.')
    monkeypatch.setattr('nettodeals.studio_routes.fetch_public', fail)
    csrf = login(client, settings)
    result = client.post('/admin/merchant/import', data={'csrf':csrf,'url':'https://shop.example/p'})
    assert result.status_code == 200 and 'HTTP 403' in result.text


def test_package_review_publish_export_and_stale(client, settings, monkeypatch):
    deal_id = draft(settings)
    csrf = login(client, settings)
    monkeypatch.setattr('nettodeals.studio_routes.product_image', lambda url: Image.new('RGBA',(700,500),'white'))
    data = dict(csrf=csrf,title='Monitor Example',shop_name='Shop',affiliate_link='https://shop.example/p',base_price='55',
                facts='IPS panel',image_url='https://shop.example/p.png',image_source='Herstellerfreigabe',rights='yes',checked='yes',
                reference_kind='merchant',reference_price='99',reference_source='https://shop.example/p')
    response = client.post(f'/admin/studio/{deal_id}/prepare', data=data)
    assert response.status_code == 200 and 'Texte prüfen' in response.text
    with connection(settings.db_path) as conn:
        pack = dict(conn.execute('SELECT * FROM studio_packages').fetchone())
        assert conn.execute('SELECT status FROM deals').fetchone()[0] == 'draft'
    for kind, size in [('feed',(1080,1350)),('story',(1080,1920))]:
        assert Image.open(BytesIO(pack[kind])).size == size
    assert 'Zuerst aktuelle Texte freigeben' in client.post(f'/admin/studio/{deal_id}/publish',data={'csrf':csrf}).text
    texts = json.loads(pack['texts'])
    texts['summary'] = 'Geprüfter Monitor-Kurztext.'
    result = client.post(f'/admin/studio/{deal_id}/approve',data=dict(csrf=csrf,expected=pack['fingerprint'],confirmed='yes',**texts))
    assert result.status_code == 200
    result = client.post(f'/admin/studio/{deal_id}/publish',data={'csrf':csrf})
    assert 'Deal veröffentlicht' in result.text
    assert 'Geprüfter Monitor-Kurztext.' in client.get('/').text
    assert 'Händler-Vergleichspreis' in client.get('/').text
    archive = client.get(f'/admin/studio/{deal_id}/download')
    assert archive.status_code == 200
    assert 'feed.png' in ZipFile(BytesIO(archive.content)).namelist()
    with connection(settings.db_path) as conn:
        conn.execute('UPDATE deals SET effective_price=60 WHERE id=?',(deal_id,))
    assert client.get(f'/admin/studio/{deal_id}/download').status_code == 409
    assert client.get(f'/admin/studio/{deal_id}/image/feed').status_code == 409


def test_gemini_failure_and_limit(settings, monkeypatch):
    init_db(settings.db_path)
    settings = replace(settings,gemini_api_key='SECRET')
    class Reply:
        status_code = 403
    monkeypatch.setattr('nettodeals.studio.requests.post',lambda *a,**k: Reply())
    for _ in range(10):
        with pytest.raises(ValueError,match='HTTP 403'):
            gemini_copy(settings,{'title':'Monitor','description':'IPS'})
    with pytest.raises(ValueError,match='Pilotlimit'):
        gemini_copy(settings,{'title':'Monitor'})


def test_optional_import_requires_one_file(client,settings):
    csrf=login(client,settings)
    response=client.post('/admin/toppreise/import',data={'csrf':csrf})
    assert response.status_code == 422 and 'mindestens eine' in response.text


def test_old_youtube_entries_get_safe_thumbnails(client,settings):
    deal_id=draft(settings)
    with connection(settings.db_path) as conn:
        conn.execute("UPDATE deals SET status='published',youtube_reviews=? WHERE id=?",(json.dumps([
            {'url':'https://www.youtube.com/watch?v=abcdefghijk','title':'Review','channel':'Test'},
            {'url':'javascript:alert(1)','title':'Bad','thumbnail':'https://bad.example/img'}]),deal_id))
    response=client.get(f'/deal/{deal_id}/camera')
    assert 'https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg' in response.text
    assert 'javascript:alert' not in response.text


def test_gemini_success_is_structured_and_private(settings, monkeypatch):
    init_db(settings.db_path)
    settings = replace(settings, gemini_api_key='PRIVATE_KEY')
    class Reply:
        status_code = 200
        def json(self):
            return {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps({
                'summary': 'Monitor mit IPS-Panel.', 'x': 'Monitor im Blick.',
                'instagram': 'Ein Monitor mit IPS-Panel.', 'tiktok': 'Monitor entdecken.'})}]}}]}
    def post(url, **kwargs):
        assert kwargs['headers']['x-goog-api-key'] == 'PRIVATE_KEY'
        assert 'PRIVATE_KEY' not in json.dumps(kwargs['json'])
        assert 'customer' not in json.dumps(kwargs['json'])
        assert kwargs['allow_redirects'] is False
        return Reply()
    monkeypatch.setattr('nettodeals.studio.requests.post', post)
    result = gemini_copy(settings, {'title': 'Monitor', 'description': 'IPS-Panel', 'customer': 'private'})
    assert result['summary'] == 'Monitor mit IPS-Panel.'


def test_single_toppreise_file(client, settings):
    from tests.test_toppreise import snapshot
    csrf = login(client, settings)
    top = snapshot(*((str(n), f'Produkt {n}', '55.00', 'Monitore') for n in range(1,51)))
    result = client.post('/admin/toppreise/import', data={'csrf': csrf},
                         files={'top100_file': ('top.html',top,'text/html')})
    assert result.status_code == 200 and '50 eindeutige Produkte' in result.text


def test_redirect_to_private_blocked_and_dns_pinned(monkeypatch):
    calls = []
    def dns(host, *args, **kwargs):
        return [(2,1,6,'',('127.0.0.1' if host == 'internal.example' else '8.8.8.8',443))]
    class Reply:
        status = 302
        headers = {'Location': 'https://internal.example/secret'}
        def close(self):
            pass
    class Pool:
        def __init__(self, ip, **kwargs):
            calls.append(ip)
            assert kwargs['server_hostname'] == 'shop.example'
            assert kwargs['assert_hostname'] == 'shop.example'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def urlopen(self, *args, **kwargs):
            assert not kwargs['redirect'] and not kwargs['retries']
            return Reply()
    monkeypatch.setattr('nettodeals.merchant.socket.getaddrinfo', dns)
    monkeypatch.setattr('nettodeals.merchant.urllib3.HTTPSConnectionPool', Pool)
    with pytest.raises(ValueError, match='Netzwerkadressen'):
        fetch_public('https://shop.example/p')
    assert calls == ['8.8.8.8']


def test_unapproved_package_cannot_publish_through_legacy_route(client, settings):
    deal_id = draft(settings)
    csrf = login(client, settings)
    with connection(settings.db_path) as conn:
        conn.execute("INSERT INTO studio_packages(deal_id,fingerprint,texts,provider,created_at) VALUES (?,?,'{}','Textvorlage','2026-01-01')", (deal_id,'stale'))
    result = client.post(f'/admin/deals/{deal_id}/publish', data={'csrf':csrf})
    assert 'gemeinsamen Editor' in result.text
    with connection(settings.db_path) as conn:
        assert conn.execute('SELECT status FROM deals').fetchone()[0] == 'draft'
