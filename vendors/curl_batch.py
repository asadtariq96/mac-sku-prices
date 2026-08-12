#!/usr/bin/env python3
"""curl-based collectors: Multitronic, NetOnNet.se, Galaxus.de, Alternate.de."""
import json, os, re, time, html as H
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CACHE = os.path.join(os.path.dirname(__file__), "..", "cache")
os.makedirs(CACHE, exist_ok=True)

def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def norm_price(s):
    s = s.replace("\xa0", " ").replace(" ", "")
    s = s.replace(",", ".")
    m = re.search(r"(\d+\.?\d*)", s)
    return float(m.group(1)) if m else None

def is_mac(s):
    s = s.lower()
    return ("mac mini" in s or "mac studio" in s) and not any(x in s for x in ["stand", "dock", "hub", "telak", "mount", "kuori", "mascara", "meikkivoide", "peitevoide", "huulikiilto", "ripsiväri", "kiinnike", "satechi", "accessory", "lisävaruste"])

# ---------- Multitronic (server-rendered HTML) ----------
def multitronic():
    out = []
    for path in ["tietokoneet-ja-tabletit/poytakoneet/apple-poytakoneet/mac-mini"]:
        try:
            body = get(f"https://www.multitronic.fi/{path}")
        except Exception as e:
            print("mt ERR", e); continue
        # product cards: names + prices
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]*Mac[^<]{0,60})</a>', body):
            url, name = m.group(1), H.unescape(m.group(2)).strip()
            if not is_mac(name): continue
            # find price near this anchor
            seg = body[m.start():m.start()+1500]
            pm = re.search(r'(\d[\d\s.,]*)\s*€', seg)
            out.append({"title": name, "price": norm_price(pm.group(1)) if pm else None, "availability": "", "url": "https://www.multitronic.fi" + url})
    # dedupe
    seen, res = set(), []
    for it in out:
        if it["title"] in seen: continue
        seen.add(it["title"]); res.append(it)
    return res

# ---------- NetOnNet.se (Next.js SSR; same catalog as .fi) ----------
def netonnet():
    out = []
    try:
        body = get("https://www.netonnet.se/search?query=mac+mini")
    except Exception as e:
        print("nn ERR", e); return out
    # product names in SSR (e.g. "name":"...") + prices
    for m in re.finditer(r'"name":"([^"]{4,90})"[^}]{0,200}?"(?:price|currentPrice|salesPrice)"\s*:\s*"?(\d[\d\s.,]*)', body):
        name, price = m.group(1), m.group(2)
        if is_mac(name) and price:
            out.append({"title": name, "price": norm_price(price), "availability": "", "url": "https://www.netonnet.se/search?query=mac+mini"})
    if not out:
        # fallback: grep lines
        for m in re.finditer(r'([^"\\]{4,80}Mac[^"\\]{0,50})', body):
            pass
    return out

# ---------- Galaxus.de (SSR HTML) ----------
def galaxus():
    out = []
    try:
        body = get("https://www.galaxus.de/search?q=mac+mini+m4&take=108")
    except Exception as e:
        print("gx ERR", e); return out
    # product blocks: name + EUR price
    for m in re.finditer(r'/en/s1/product/([^"]+)"[^>]*>.*?EUR\s*([\d.,]+)', body, re.S):
        slug, price = m.group(1), m.group(2)
        name = slug.replace("-", " ")
        if is_mac(name):
            out.append({"title": name, "price": norm_price(price), "availability": "", "url": "https://www.galaxus.de/en/s1/product/" + slug})
    return out

# ---------- Alternate.de (SSR HTML) ----------
def alternate():
    out = []
    try:
        body = get("https://www.alternate.de/listing.xhtml?q=mac+mini")
    except Exception as e:
        print("alt ERR", e); return out
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]*Mac[^<]{0,60})</a>', body):
        url, name = m.group(1), H.unescape(m.group(2)).strip()
        if not is_mac(name): continue
        seg = body[m.start():m.start()+1200]
        pm = re.search(r'(\d[\d\s.,]*)\s*€', seg)
        out.append({"title": name, "price": norm_price(pm.group(1)) if pm else None, "availability": "", "url": "https://www.alternate.de" + url})
    seen, res = set(), []
    for it in out:
        if it["title"] in seen: continue
        seen.add(it["title"]); res.append(it)
    return res

if __name__ == "__main__":
    for name, fn in [("multitronic", multitronic), ("netonnet", netonnet), ("galaxus", galaxus), ("alternate", alternate)]:
        try:
            items = fn()
            fpath = os.path.join(CACHE, f"vendor_{name}.json")
            if not items and os.path.exists(fpath):
                print(f"== {name}: 0 items (fetch failed/blocked) — keeping previous cache")
                continue
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump({"store": name, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "items": items}, f, ensure_ascii=False, indent=1)
            print(f"== {name}: {len(items)} items")
            for it in items[:15]:
                print(f"   {it['title'][:60]:60} {it['price']}")
        except Exception as e:
            print(name, "FAILED", repr(e)[:150])
        time.sleep(1)
