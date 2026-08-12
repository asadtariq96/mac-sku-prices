#!/usr/bin/env python3
"""Alternate.de collector (SSR HTML)."""
import json, os, re, time, html as H
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CACHE = os.path.join(os.path.dirname(__file__), "..", "cache")

def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def norm(s):
    s = s.replace("\xa0", "").replace(" ", "")
    m = re.search(r"(\d+[.,]\d+)", s)
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None

body = get("https://www.alternate.de/listing.xhtml?q=mac+mini")
items = []
for m in re.finditer(r'<div class="product-name font-weight-bold"><span>[^<]*</span>\s*([^<]{3,80})</div>', body):
    name = H.unescape(m.group(1)).strip()
    if "mac mini" not in name.lower() and "mac studio" not in name.lower():
        continue
    block = body[m.start():m.start()+6000]
    sub = re.search(r'product-name-sub">([^<]+)</span>', block)
    spec = re.search(r"Speicher:\s*([^<]+)</li>", block)
    price = re.search(r'<span class="price ">€\s*([\d.,]+)</span>', block)
    uvp = re.search(r'line-through">€\s*([\d.,]+)</span>', block)
    avail = re.search(r'delivery-info text-right"><span class="font-weight-bold">([^<]+)</span>', block)
    href = re.search(r'href="([^"]+)"[^>]*>', body[m.start()-2500:m.start()])
    items.append({
        "title": "Apple " + name + ((" " + sub.group(1).strip()) if sub else ""),
        "spec": spec.group(1).strip() if spec else "",
        "price": norm(price.group(1)) if price else None,
        "uvp": norm(uvp.group(1)) if uvp else None,
        "availability": avail.group(1).strip() if avail else "",
        "url": "https://www.alternate.de" + href.group(1) if href else "",
    })

with open(os.path.join(CACHE, "vendor_alternate.json"), "w", encoding="utf-8") as f:
    json.dump({"store": "alternate", "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "items": items}, f, ensure_ascii=False, indent=1)
print("alternate:", len(items))
for it in items:
    print(f"   {it['title'][:55]:55} {it['price']} (UVP {it['uvp']}) | {it['spec'][:40]:40} | {it['availability'][:40]}")
