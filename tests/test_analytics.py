import pytest


@pytest.mark.parametrize('path', ['/', '/datenschutz', '/impressum', '/vergangene-deals', '/steckbriefe'])
def test_public_consent_and_csp(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.text.count('src="/static/analytics.js?v=1"') == 1
    assert 'id="analytics-consent"' in response.text
    assert 'src="https://www.googletagmanager.com' not in response.text
    policy = response.headers['content-security-policy']
    assert 'https://www.googletagmanager.com' in policy
    assert "'unsafe-inline'" not in policy
    assert "'unsafe-eval'" not in policy


def test_admin_has_no_analytics(client):
    response = client.get('/admin/login')
    assert response.status_code == 200
    assert '/static/analytics.js' not in response.text
    assert 'analytics-consent' not in response.text
    assert 'googletagmanager' not in response.headers['content-security-policy']


def test_analytics_assets_and_privacy(client):
    assert client.get('/static/analytics.js').status_code == 200
    assert client.get('/static/analytics.css').status_code == 200
    privacy = client.get('/datenschutz').text
    assert 'G-GQGD9NXG70' in privacy
    assert '180 Tage' in privacy
