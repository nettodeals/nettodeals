from __future__ import annotations

from nettodeals.services import (
    effective_price,
    map_awin_offer,
    map_tradedoubler_product,
    map_tradedoubler_voucher,
    safe_money,
)


def test_money_is_finite_and_bounded():
    assert safe_money("CHF 1'299.95") == 1299.95
    assert safe_money("NaN") == 0
    assert safe_money(float("inf")) == 0
    assert effective_price(100, 20, 5) == 75


def test_awin_nested_voucher_code():
    candidate = map_awin_offer(
        {
            "promotionId": 10,
            "type": "voucher",
            "title": "20 Franken Rabatt",
            "advertiser": {"id": 4, "name": "Shop"},
            "url": "https://shop.example/sale",
            "urlTracking": "https://track.example/sale",
            "voucher": {"code": "AWIN20"},
            "endDate": "2027-01-01T00:00:00.000Z",
        }
    )
    assert candidate
    assert candidate.coupon_code == "AWIN20"
    assert candidate.affiliate_link == "https://track.example/sale"
    assert candidate.expires_at.startswith("2027-01-01")


def test_tradedoubler_nested_product_offer():
    candidates = map_tradedoubler_product(
        {
            "name": "Notebook Pro",
            "description": "Schnell",
            "categories": [{"name": "Notebooks"}],
            "offers": [
                {
                    "id": "offer-1",
                    "programName": "Swiss Shop",
                    "productUrl": "https://track.example/notebook",
                    "price": {"value": "1199.00", "currency": "CHF"},
                }
            ],
        },
        123,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.base_price == 1199
    assert candidate.shop_name == "Swiss Shop"
    assert candidate.category == "Notebooks"
    assert candidate.affiliate_link == "https://track.example/notebook"


def test_tradedoubler_voucher_official_link_fields():
    candidate = map_tradedoubler_voucher(
        {
            "id": 1,
            "programName": "Shop",
            "title": "Rabatt",
            "code": "SAVE10",
            "defaultTrackUri": "http://track.example/voucher",
            "landingUrl": "https://shop.example/sale",
            "discountAmount": 10,
            "isPercentage": True,
        }
    )
    assert candidate
    assert candidate.affiliate_link == "http://track.example/voucher"
    assert "10% Rabatt" in candidate.description
