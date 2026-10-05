import json
from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from nettodeals.db import connection
from nettodeals.gemini_settings import effective_settings, normalize_api_key
from nettodeals.social_otter import ASSETS, GOALS, POSES, build_texts
from nettodeals.studio import gemini_copy
from tests.test_app import login
from tests.test_deal_workflow import draft


@pytest.mark.parametrize("key", ["AIza" + "a"*35, "AQ." + "abc-_.123="*90, "AQ." + "z"*3500])
def test_new_keys_round_trip_without_reflection(client, settings, monkeypatch, key):
    csrf = login(client, settings)
    response = client.post("/admin/settings/gemini/save", data={
        "csrf": csrf, "api_key": key, "model": "gemini-3.1-flash-lite", "enabled": "yes"})
    assert "Einstellungen gespeichert" in response.text and key not in response.text
    assert effective_settings(settings).gemini_api_key == key
    assert key not in client.get("/api/status").text
    calls = []

    class Reply:
        status_code = 200
        def json(self):
            return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(
                {field: "Sachlicher Entwurf." for field in ("summary", "x", "instagram", "tiktok")})}]}}]}

    def post(url, **kwargs):
        assert key not in url
        assert kwargs["headers"]["x-goog-api-key"] == key
        calls.append(1)
        return Reply()
    monkeypatch.setattr("nettodeals.studio.requests.post", post)
    assert gemini_copy(settings, {"title": "Monitor"})["summary"] == "Sachlicher Entwurf."
    assert calls


def test_quote_cleanup_and_unsafe_keys():
    key = "AQ." + "abc.def_-"*40
    assert normalize_api_key(' “' + key + '” ') == key
    for bad in [key + "\r\nX-Header: bad", key + " abc", key + "\u200b", "a"*4097]:
        with pytest.raises(ValueError):
            normalize_api_key(bad)


def test_otto_assets_have_alpha_and_six_poses():
    for pose in POSES:
        with Image.open(ASSETS / (pose + ".png")) as image:
            assert image.size == (512, 512) and image.mode == "RGBA"
            assert image.getchannel("A").getextrema()[0] == 0


def test_social_workflow_slides_review_and_staleness(client, settings, monkeypatch):
    deal_id = draft(settings)
    csrf = login(client, settings)
    monkeypatch.setattr("nettodeals.studio_routes.product_image", lambda url: Image.new("RGBA", (600, 400), "white"))
    data = dict(csrf=csrf, title="Monitor", shop_name="Shop", affiliate_link="https://shop.example/p",
                base_price=55, facts="IPS", image_url="https://shop.example/p.png",
                image_source="Herstellerfreigabe", rights="yes", checked="yes",
                social_hook="Monitor fürs Homeoffice?", social_benefit="IPS-Panel",
                social_caveat="Kein USB-C", social_goal="follow", otto_pose="explain")
    response = client.post(f"/admin/studio/{deal_id}/prepare", data=data)
    assert response.status_code == 200 and "Karte 3 herunterladen" in response.text
    for i in (1, 2, 3):
        image = client.get(f"/admin/studio/{deal_id}/image/slide-{i}")
        assert image.status_code == 200
        assert Image.open(BytesIO(image.content)).size == (1080, 1920)
    with connection(settings.db_path) as conn:
        pack = dict(conn.execute("SELECT * FROM studio_packages WHERE deal_id=?", (deal_id,)).fetchone())
    texts = json.loads(pack["texts"])
    assert "Folge NettoDeals" in texts["tiktok"]
    assert "Kein USB-C" in texts["tiktok"]
    archive = ZipFile(BytesIO(client.get(f"/admin/studio/{deal_id}/download").content))
    assert all(f"tiktok-{i:02}.png" in archive.namelist() for i in (1, 2, 3))
    assert client.get(f"/d/{deal_id}").status_code == 404
    approved = client.post(f"/admin/studio/{deal_id}/approve",
        data=dict(csrf=csrf, expected=pack["fingerprint"], confirmed="yes", **texts))
    assert approved.status_code == 200
    with connection(settings.db_path) as conn:
        conn.execute("UPDATE deals SET social_goal='visit' WHERE id=?", (deal_id,))
    assert client.get(f"/admin/studio/{deal_id}/image/slide-1").status_code == 409
    assert client.get(f"/admin/studio/{deal_id}/download").status_code == 409


@pytest.mark.parametrize("goal", GOALS)
def test_social_limits_and_no_invented_discount(settings, goal):
    deal = dict(id=1, title="Monitor " + "M"*290, effective_price=99, shop_name="S"*120,
                link_type="editorial", social_goal=goal, social_hook="H"*140,
                social_audience="A"*140, social_benefit="B"*140, social_caveat="C"*140,
                social_question="Q"*140)
    texts = build_texts(deal, replace(settings, site_url="https://nettodeals.ch"),
                        {field: "Text "*200 for field in ("summary","instagram","tiktok")})
    assert len(texts["instagram"]) <= 2200 and len(texts["tiktok"]) <= 2200
    assert len(texts["x"]) <= 280
    assert "UVP" not in texts["tiktok"] and "Link in Bio" not in texts["tiktok"]


def test_short_link_status(client, settings):
    deal_id = draft(settings)
    assert client.get(f"/d/{deal_id}").status_code == 404
    for state in ("published", "expired"):
        with connection(settings.db_path) as conn:
            conn.execute("UPDATE deals SET status=? WHERE id=?", (state, deal_id))
        response = client.get(f"/d/{deal_id}", follow_redirects=False)
        assert response.status_code == 302 and response.headers["location"].startswith(f"/deal/{deal_id}/")


def test_invalid_social_options_do_not_change_deal(client, settings):
    deal_id = draft(settings)
    csrf = login(client, settings)
    response = client.post(f"/admin/studio/{deal_id}/prepare", data=dict(
        csrf=csrf, title="Changed", shop_name="Shop", affiliate_link="https://shop.example/p",
        base_price=20, otto_pose="../../other", social_goal="bad"))
    assert "Social-Felder" in response.text
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT title FROM deals WHERE id=?", (deal_id,)).fetchone()[0] != "Changed"
