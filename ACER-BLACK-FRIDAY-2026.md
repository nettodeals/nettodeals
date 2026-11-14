# Acer Black Friday & Cyber Monday 2026

## Zweck

Die öffentliche Kampagnenseite liegt unter `/acer-black-friday`. Sie zeigt ausschliesslich veröffentlichte, noch gültige Deals, bei denen Händler, Datenquelle oder Produkttitel Acer enthalten. Ohne freigegebene Angebote wird die Seite mit `noindex` ausgeliefert. Die Seite wird in die Sitemap aufgenommen.

## Awin verbinden

Die bestehende Awin-Synchronisierung verwendet:
- `AWIN_PUBLISHER_ID`
- `AWIN_API_TOKEN`
- `AWIN_REGIONS=CH`

Publisher-ID und API-Token gehören nur in die Server-Umgebung (z. B. `.env` auf dem Host), niemals in GitHub oder Browser-Code. Danach im Adminbereich **Quellen synchronisieren** ausführen. Die bestehende Awin-API-Abfrage importiert aktive, beigetretene Promotions für die konfigurierten Regionen als Entwürfe. Acer-Aktionen werden anhand des Advertiser-Namens Acer auf der Kampagnenseite sichtbar, sobald sie redaktionell freigegeben sind.

**Wichtige Abgrenzung:** Die aktuell implementierte Awin-Schnittstelle importiert Promotions/Gutscheine, nicht den vollständigen Awin-Produktkatalog. Produktangebote mit konkretem Modell, CHF-Preis und Produktbild müssen deshalb über einen verfügbaren Produktfeed oder manuell über den Admin-Deal-Editor ergänzt werden. Keine Produktpreise oder Rabatte aus Promotionstiteln ableiten.

## Produkte veröffentlichen

1. Für jedes Produkt die exakte Modell-/SKU-Variante, den Schweizer Endpreis, Lieferkosten, Lagerbestand und Aktionsende im Händlerkonto bzw. Shop prüfen.
2. Den Awin-Trackinglink verwenden. Im manuellen Deal-Editor den Shop als Acer (oder den tatsächlichen Shopnamen) erfassen, Linkart **Affiliate-Link** wählen und den geprüften Preis eintragen.
3. Nur Bilder verwenden, deren Nutzungsrecht für Website und Social Media vorliegt; Rechtegeber und Bildquelle dokumentieren.
4. Falls ein Rabatt behauptet wird, einen belegten Vergleichspreis und dessen Quelle eintragen. Ohne Nachweis keinen Prozent-Rabatt nennen.
5. Im Deal-Studio Produktfakten, Einschränkungen und Preis prüfen. Social-Texte und Grafiken erstellen, redaktionell kontrollieren und freigeben.
6. Deal veröffentlichen. Er erscheint dann automatisch auf `/acer-black-friday`.

## Social Media

Das Deal-Studio erstellt je Deal:
- X-Text mit maximal 280 Zeichen und Deal-Link,
- Instagram- und TikTok-Caption,
- TikTok-Sprechskript und passende Grafiken.

Bei Acer-Produkten werden automatisch die Kampagnen-Hashtags `#Acer #BlackFridayCH #CyberMondayCH` ergänzt. Die Inhalte werden nicht automatisch auf externe Plattformen gepostet. Affiliate-Werbung muss im Beitrag klar gekennzeichnet bleiben. Preisstand, Aktionsbedingungen und Modellvariante vor jedem Posting nochmals prüfen.

## Conversion- und Qualitätsregeln

- Pro Beitrag ein Produkt, eine Zielgruppe/ein konkreter Nutzen und ein klarer CTA.
- Direkt auf die NettoDeals-Detailseite verlinken, nicht auf die Startseite.
- Modellnummern und Varianten exakt nennen.
- Rabatt nur mit belegtem Vergleichspreis ausweisen.
- Ablaufdatum und Preis regelmässig prüfen; abgelaufene Deals werden nicht mehr als aktive Kaufangebote angezeigt.
- Klicks werden bereits über `/go/{id}` aggregiert. Für Awin-Conversions sind zusätzlich die Awin-Reports massgeblich; ein Klick ist keine Conversion.

## Saisontermine 2026

- Black Friday: 27. November 2026
- Cyber Monday: 30. November 2026

Die Datumsangaben sind redaktionelle Kampagnenhinweise; konkrete Acer-Aktionen gelten nur gemäss den Bedingungen des jeweiligen Advertisers/Händlers.
