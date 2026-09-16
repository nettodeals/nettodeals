from __future__ import annotations

from email import policy
from email.message import EmailMessage

import pytest

from nettodeals.toppreise import SnapshotError, extract_snapshot_html, parse_snapshot


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


def mhtml_archive(html: str) -> bytes:
    archive = EmailMessage()
    archive["MIME-Version"] = "1.0"
    archive.set_type("multipart/related")
    page = EmailMessage()
    page["Content-Location"] = "https://www.toppreise.ch/topprodukte"
    page.set_content(html, subtype="html", charset="utf-8", cte="quoted-printable")
    archive.attach(page)
    image = EmailMessage()
    image["Content-Location"] = "https://www.toppreise.ch/logo.png"
    image.set_content(b"not imported", maintype="image", subtype="png", cte="base64")
    archive.attach(image)
    return archive.as_bytes(policy=policy.default)


def test_extract_chromium_mhtml_and_parse_product():
    html = snapshot(("818734", "APPLE AirPods Pro 3", "180.10", "Kopfhoerer"))
    extracted = extract_snapshot_html(
        mhtml_archive(html),
        filename="topprodukte.mht",
        content_type="multipart/related",
    )

    assert "APPLE AirPods Pro 3" in extracted
    result = parse_snapshot(extracted, collection="top100")
    assert [candidate.source_id for candidate in result.candidates] == ["818734"]


def test_extract_mhtml_rejects_archive_without_html():
    archive = EmailMessage()
    archive["MIME-Version"] = "1.0"
    archive.set_type("multipart/related")
    image = EmailMessage()
    image.set_content(b"image", maintype="image", subtype="png", cte="base64")
    archive.attach(image)

    with pytest.raises(SnapshotError, match="kein HTML-Inhalt"):
        extract_snapshot_html(archive.as_bytes(), filename="snapshot.mhtml")


def test_extract_snapshot_rejects_unknown_file_type():
    with pytest.raises(SnapshotError, match="Erlaubt sind"):
        extract_snapshot_html(b"<html></html>", filename="snapshot.txt")
