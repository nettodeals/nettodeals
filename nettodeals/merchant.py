"""Bounded public HTTPS imports. DNS is resolved once and pinned per connection."""
import ipaddress
import json
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import urllib3

from .security import normalize_external_url
from .services import safe_money


def fetch_public(url, limit=2_000_000):
    for _ in range(4):
        url = normalize_external_url(url)
        parsed = urlsplit(url)
        if not url or parsed.port not in (None, 443):
            raise ValueError("Nur öffentliche HTTPS-Adressen auf Port 443 sind erlaubt.")
        host = parsed.hostname
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
            if not addresses or any((not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast) for ip in addresses):
                raise ValueError("Interne oder reservierte Netzwerkadressen sind nicht erlaubt.")
            ip = sorted(addresses)[0]
            with urllib3.HTTPSConnectionPool(ip, port=443, server_hostname=host,
                    assert_hostname=host, ssl_context=ssl.create_default_context(),
                    timeout=urllib3.Timeout(total=20, connect=5, read=10)) as pool:
                response = pool.urlopen("GET", parsed.path + ("?" + parsed.query if parsed.query else ""),
                    headers={"Host": host, "User-Agent": "NettoDeals/3.5 editorial-import", "Accept-Encoding": "identity"},
                    redirect=False, retries=False, preload_content=False)
                try:
                    if response.status in (301, 302, 303, 307, 308):
                        url = urljoin(url, response.headers.get("Location", ""))
                        continue
                    if response.status != 200:
                        raise ValueError(f"Händlerabruf HTTP {response.status}. Angaben bitte manuell ergänzen.")
                    data = response.read(limit + 1)
                    if len(data) > limit:
                        raise ValueError("Quelldatei zu gross.")
                    return data, url
                finally:
                    response.close()
        except (OSError, urllib3.exceptions.HTTPError) as exc:
            raise ValueError("Quelle nicht erreichbar. Angaben bitte manuell ergänzen.") from exc
    raise ValueError("Zu viele Weiterleitungen.")


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.scripts = {}, []
        self.record = False
        self.buffer = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            self.meta[attrs.get("property", attrs.get("name", ""))] = attrs.get("content", "")
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.record, self.buffer = True, ""

    def handle_data(self, data):
        if self.record:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag == "script" and self.record:
            self.scripts.append(self.buffer)
            self.record = False


def parse_product(data, url):
    parser = Metadata()
    parser.feed(data.decode("utf-8", errors="replace"))
    products = []
    def walk(node, depth=0):
        if depth > 20:
            return
        if isinstance(node, list):
            for child in node:
                walk(child, depth + 1)
        elif isinstance(node, dict):
            types = node.get("@type", [])
            if types == "Product" or isinstance(types, list) and "Product" in types:
                products.append(node)
            elif "@graph" in node:
                walk(node["@graph"], depth + 1)
    for script in parser.scripts:
        try:
            walk(json.loads(script))
        except (ValueError, RecursionError):
            continue
    product = products[0] if len(products) == 1 else {}
    offers = product.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if len(offers) == 1 else {}
    if not isinstance(offers, dict):
        offers = {}
    currency = offers.get("priceCurrency", parser.meta.get("product:price:currency", ""))
    price = safe_money(offers.get("price", parser.meta.get("product:price:amount", 0))) if currency == "CHF" else 0
    image = product.get("image", parser.meta.get("og:image", ""))
    if isinstance(image, list):
        image = image[0] if image else ""
    if isinstance(image, dict):
        image = image.get("url", "")
    facts = str(product.get("description", parser.meta.get("og:description", "")))[:3000]
    # Treat all extracted prose as untrusted source material, never instructions.
    return {
        "title": str(product.get("name", parser.meta.get("og:title", "Händlerangebot prüfen")))[:300],
        "shop_name": urlsplit(url).hostname,
        "base_price": price, "image_url": normalize_external_url(urljoin(url, str(image))) if image else "",
        "description": facts, "affiliate_link": url,
        "notes": "Automatisch extrahiert; Modell, CHF-Preis, Lieferkosten, Verfügbarkeit und Bildrechte prüfen. "
                 + ("Kein eindeutiger CHF-Preis erkannt. " if not price else "")
                 + ("Mehrere Produkte erkannt; bitte konkrete Variante ergänzen." if len(products) > 1 else ""),
    }
