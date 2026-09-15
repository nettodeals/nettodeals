from __future__ import annotations

from nettodeals.toppreise import parse_snapshot


def snapshot(*products: tuple[str, str, str, str], period: int | None = None) -> str:
    radios = ""
    if period is not None:
        radios = f'<input class="f_timePeriod" value="{period}" checked>'
    cards = "".join(
        f"""
        <a class="Plugin_Product" data-entity-id="{entity_id}"
           href="/preisvergleich/{category}/{slug}-p{entity_id}">
          <div class="product-name">{title}</div>
          <div class="priceContainer shippingPrice"><span class="Plugin_Price">{price}</span></div>
        </a>
        """
        for entity_id, title, price, category in products
        for slug in [title.lower().replace(" ", "-")]
    )
    return f"<html><body>{radios}{cards}</body></html>"


def test_parse_toppreise_snapshot_creates_editorial_candidates():
    html = snapshot(("818734", "APPLE AirPods Pro 3", "180.10", "Kopfhoerer"))
    result = parse_snapshot(html, collection="top100")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.source == "toppreise"
    assert candidate.source_id == "818734"
    assert candidate.link_type == "editorial"
    assert candidate.source_name == "Toppreise.ch"
    assert candidate.price_type == "from"
    assert candidate.base_price == 180.10
    assert candidate.category == "Kopfhoerer"
    assert candidate.affiliate_link.startswith("https://www.toppreise.ch/preisvergleich/")
    assert "Keine Provision" in candidate.description


def test_dynamic_new_toppreise_snapshot_does_not_depend_on_radio_attribute():
    html = snapshot(("1", "Produkt", "99.00", "Elektronik"), period=8)
    result = parse_snapshot(html, collection="new48")
    assert len(result.candidates) == 1


def test_snapshot_volume_guard_detects_incomplete_page():
    html = snapshot(("1", "Produkt", "99.00", "Elektronik"))
    try:
        parse_snapshot(html, collection="top100", minimum_items=50)
    except ValueError as exc:
        assert "mindestens 50" in str(exc)
    else:
        raise AssertionError("Unvollständiger Snapshot wurde akzeptiert")
