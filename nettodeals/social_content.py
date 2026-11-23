"""Compact, product-first social content for NettoDeals. No mascot artwork."""
from io import BytesIO
from datetime import date
from PIL import Image, ImageDraw, ImageOps
from .social_cards import _font, _wrap
from .db import now_iso

GOALS = ("follow", "visit", "discuss", "save")
USP = "Schweizer Deals. Nutzen statt Preisplakat."

def angle(deal):
    title=str(deal.get("title",""))
    return {"hook": deal.get("social_hook") or "Ein Angebot, das sich genauer anzuschauen lohnt?",
            "audience":deal.get("social_audience") or "",
            "benefit":deal.get("social_benefit") or "",
            "caveat":deal.get("social_caveat") or "",
            "question":deal.get("social_question") or "Wäre das für dich interessant?"}

def cta(deal):
    return {"follow":"Folge NettoDeals für ausgewählte Schweizer Deals.",
            "visit":f"Details: nettodeals.ch/d/{deal['id']}",
            "discuss":angle(deal)["question"],
            "save":"Speichere den Deal und prüfe den Preis vor dem Kauf."}.get(deal.get("social_goal") or "follow","Folge NettoDeals.")

def _clean_copy(copy,key,limit):
    value=copy.get(key,"") if isinstance(copy,dict) else ""
    return value.strip()[:limit] if isinstance(value,str) else ""

def build_texts(deal, settings, copy=None):
    from .studio import comparison
    a=angle(deal); price=f"CHF {deal['effective_price']:.2f}"; ref,label=comparison(deal)
    saving=f"{round((ref-deal['effective_price'])/ref*100)} % unter Vergleichspreis" if ref else ""
    url=settings.site_url+f"/d/{deal['id']}"; title=deal["title"]
    disclosure="Werbung · Affiliate-Link." if deal["link_type"]=="affiliate" else "Redaktioneller Link."
    date_text=str(deal.get("price_checked_at") or now_iso())[:10]
    tags="#NettoDeals #DealsSchweiz"+(" #Acer #BlackFridayCH #CyberMondayCH" if "acer" in (str(deal.get("shop_name",""))+title).casefold() else "")
    summary=_clean_copy(copy,"summary",240) or f"{title} · {price}"+(f" · {saving}" if saving else "")
    x=f"{title[:95]} · {price} bei {deal['shop_name'][:28]}. {disclosure} {url}"
    if len(x)>280: x=x[:max(1,276-len(url))].rstrip()+"… "+url
    ig="\n".join(p for p in (a["hook"][:90],title[:130],_clean_copy(copy,"instagram",120),f"{price} · {deal['shop_name']}",saving,f"Mehr: {url}",disclosure,tags) if p)
    tt="\n".join(p for p in (title[:130],_clean_copy(copy,"tiktok",100),f"{price} bei {deal['shop_name']}",saving,f"nettodeals.ch/d/{deal['id']}",disclosure,tags) if p)
    script=f"Hook: {a['hook'][:70]}\nProdukt: {title[:140]}\nVorteil: {a['benefit'][:110] or 'Fakten beim Händler prüfen.'}\nPreis: {price}\nCTA: Details auf NettoDeals ansehen."
    footer=f"Stand {date_text} · Preis und Verfügbarkeit können sich ändern."
    return {"summary":summary+"\nKein eigener Produkttest.","x":x,"instagram":ig+"\n"+footer,"tiktok":tt+"\n"+footer,"script":script}

def render_sequence(deal, photo):
    """Create three concise, product-led portrait cards without mascot artwork."""
    frames=[]; texts=[deal["title"][:110],f"CHF {deal['effective_price']:.2f}",angle(deal)["benefit"][:100] or "Produktdetails und Verfügbarkeit prüfen."]
    for i,text in enumerate(texts):
        canvas=Image.new("RGB",(1080,1920),"#f7f9ff"); draw=ImageDraw.Draw(canvas)
        draw.rectangle((0,0,1080,18),fill="#365fd5")
        draw.text((80,90),"NETTODEALS  /  SCHWEIZER DEAL-RADAR",font=_font(30),fill="#5c64a8")
        draw.text((80,170),f"{i+1:02d}  /  03",font=_font(30),fill="#7a83a1")
        draw.rounded_rectangle((60,260,1020,1570),radius=44,fill="#ffffff",outline="#e5e9f3",width=3)
        product=ImageOps.contain(photo.convert("RGB"),(850,760))
        canvas.paste(product,(540-product.width//2,700-product.height//2))
        font=_font(66 if i==0 else 76)
        lines=_wrap(draw,text,font,860)
        while len(lines)>4 and font.size>42:
            font=_font(font.size-4); lines=_wrap(draw,text,font,860)
        y=1160
        for line in lines:
            draw.text((95,y),line,font=font,fill="#18233a");y+=font.size+18
        draw.text((95,1660),USP,font=_font(32),fill="#5c64a8")
        draw.text((95,1765),"Preis und Verfügbarkeit beim Händler prüfen.",font=_font(27),fill="#66718a")
        frames.append(canvas)
    output=[]
    for canvas in frames:
        buf=BytesIO(); canvas.save(buf,format="PNG"); output.append(buf.getvalue())
    return output
