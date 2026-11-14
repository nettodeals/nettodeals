from types import SimpleNamespace

from nettodeals.social_otter import build_texts


def test_x_copy_is_bounded_and_keeps_deal_url():
    deal = {
        "id": 42,
        "title": "Premium Monitor " * 30,
        "shop_name": "Schweizer Fachhändler",
        "effective_price": 299.9,
        "link_type": "affiliate",
        "price_checked_at": "2026-11-14",
        "comparison_price": 0,
        "comparison_source": "",
        "manufacturer_uvp": 0,
        "uvp_source_url": "",
        "social_hook": "Passt dieser Monitor zu deinem Setup?",
        "social_audience": "",
        "social_benefit": "",
        "social_caveat": "",
        "social_question": "Wofür würdest du ihn nutzen?",
        "social_goal": "follow",
    }

    texts = build_texts(deal, SimpleNamespace(site_url="https://nettodeals.ch"))

    assert len(texts["x"]) <= 280
    assert texts["x"].endswith("https://nettodeals.ch/d/42")
    assert "Affiliate-Link" in texts["x"]
    assert "Kein eigener Produkttest." in texts["script"]


def test_invalid_ai_social_fields_fall_back_to_editorial_copy():
    deal = {
        "id": 7,
        "title": "Kompakter Monitor",
        "shop_name": "Shop",
        "effective_price": 149,
        "link_type": "editorial",
        "price_checked_at": "2026-11-14",
        "comparison_price": 0,
        "comparison_source": "",
        "manufacturer_uvp": 0,
        "uvp_source_url": "",
        "social_goal": "follow",
    }

    texts = build_texts(
        deal,
        SimpleNamespace(site_url="https://nettodeals.ch"),
        {"summary": ["not", "plain text"], "instagram": None, "tiktok": 123},
    )

    assert "Kompakter Monitor" in texts["summary"]
    assert "Kompakter Monitor" in texts["instagram"]
    assert "Kompakter Monitor" in texts["tiktok"]
    assert "Redaktioneller Link ohne Affiliate-Provision." in texts["instagram"]


def test_acer_social_drafts_include_seasonal_campaign_tags():
    deal = {
        "id": 18,
        "title": "Acer Swift Notebook",
        "shop_name": "Acer Schweiz",
        "effective_price": 899,
        "link_type": "affiliate",
        "price_checked_at": "2026-11-14",
        "comparison_price": 0,
        "comparison_source": "",
        "manufacturer_uvp": 0,
        "uvp_source_url": "",
        "social_goal": "visit",
    }
    texts = build_texts(deal, SimpleNamespace(site_url="https://nettodeals.ch"))
    assert "#Acer" in texts["instagram"]
    assert "#BlackFridayCH" in texts["instagram"]
    assert "#CyberMondayCH" in texts["tiktok"]
    assert "https://nettodeals.ch/d/18" in texts["x"]
