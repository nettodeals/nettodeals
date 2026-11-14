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


## Bestätigte Acer-Aktionen CH-DE (Angaben aus der Awin-Nachricht)

| Aktion | Zeitraum (CET) | Ziel |
|---|---|---|
| Extra-Rabatt, Code BONUS | 20.11.2026 15:00 – 24.11.2026 09:00 | https://store.acer.com/de-ch |
| Black Friday, bis zu 50% | 26.11.2026 12:00 – 30.11.2026 08:00 | https://store.acer.com/de-ch/spezialangebote/deals |
| Cyber Monday, bis zu 50% | 30.11.2026 08:00 – 01.12.2026 09:00 | https://store.acer.com/de-ch/spezialangebote/deals |

Für beide Hauptaktionen gilt laut Aktionsinfo: Rabatt wird automatisch im Warenkorb abgezogen. Die bis zu 50% gelten für ausgewählte Produkte, nicht pauschal für das gesamte Sortiment.

Kategorie-Ziele aus der Aktionsinfo:
- Laptops: `/de-ch/spezialangebote/deals/laptops`
- Desktops: `/de-ch/special-offers/deals/desktop-pcs`
- Monitore: `/de-ch/spezialangebote/deals/desktop-pcs` (URL laut Nachricht; vor Bewerbung prüfen, da sie wie die Desktop-Zielseite aussieht)
- Gaming: `/de-ch/spezialangebote/deals/gaming`
- Zubehör: `/de-ch/spezialangebote/deals/zubehor`

## Social Copy zur schnellen manuellen Verwendung

**BONUS – Instagram**
> 🎁 Extra-Rabatt bei Acer! Mit dem Code BONUS sicherst du dir vom 20. bis 24. November zusätzliche Rabatte auf ausgewählte Black-Friday-Angebote. Der Rabatt wird gemäss Aktionsbedingungen im Warenkorb berücksichtigt. Jetzt Acer-Angebote entdecken. Werbung / Affiliate-Link.

**Black Friday – Instagram**
> 🖥️ Acer Black Friday für die Schweiz: Bis zu 50% Rabatt auf ausgewählte Produkte! Die Aktion läuft vom 26. November, 12:00 Uhr, bis 30. November, 08:00 Uhr (CET). Der Rabatt wird automatisch im Warenkorb abgezogen. Prüfe die verfügbaren Modelle und Preise direkt im Acer Store. Werbung / Affiliate-Link.

**Cyber Monday – TikTok/Reel**
> Noch auf der Suche nach einem Laptop, Monitor oder Gaming-Upgrade? Beim Acer Cyber Monday gibt es laut Aktionsinfo bis zu 50% Rabatt auf ausgewählte Produkte. Nur vom 30. November, 08:00 Uhr, bis 1. Dezember, 09:00 Uhr (CET). Rabatt wird automatisch im Warenkorb abgezogen. Details über den Link. Werbung / Affiliate-Link.

Vor Veröffentlichung personalisierten Awin-Trackinglink einsetzen, Affiliate-Hinweis sichtbar halten und Bedingungen/Verfügbarkeit erneut prüfen. Social Copy nicht als Behauptung eines pauschalen Rabatts formulieren.
