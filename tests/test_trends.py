from __future__ import annotations

from nettodeals.db import connection, init_db, upsert_deal
from nettodeals.services import DealCandidate
from nettodeals.trends import match_quality, parse_google_trends_rss, store_and_apply_trends

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item><title>iPhone 18</title><ht:approx_traffic>10K+</ht:approx_traffic><pubDate>today</pubDate></item>
    <item><title>Eishockey Resultate</title><ht:approx_traffic>500+</ht:approx_traffic></item>
  </channel>
</rss>"""


def test_google_trends_rss_and_product_matching(tmp_path):
    terms = parse_google_trends_rss(RSS)
    assert terms[0].term == "iPhone 18"
    assert terms[0].traffic == 10_000
    assert match_quality("Apple iPhone 18 Pro 256 GB", "iPhone 18") > 0.5
    assert match_quality("Apple iPhone 18 Pro 256 GB", "Eishockey Resultate") == 0

    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    values = DealCandidate(
        title="Apple iPhone 18 Pro 256 GB",
        category="Smartphones",
        base_price=1200,
        shop_name="Shop",
        affiliate_link="https://example.test/phone",
        source="manual",
        source_id="phone",
    ).values(status="published")
    upsert_deal(db_path, values)
    assert store_and_apply_trends(db_path, terms) == 2
    with connection(db_path) as conn:
        score = conn.execute("SELECT trend_score FROM deals").fetchone()[0]
    assert score > 20
