#!/usr/bin/env python3
"""Gigantti collector via Algolia (signed key expires ~1h; refresh by visiting gigantti.fi search page in a browser)."""
import json, os, time, urllib.request, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CACHE = os.path.join(os.path.dirname(__file__), "..", "cache")
os.makedirs(CACHE, exist_ok=True)

# Signed key captured 2026-08-12 01:25 local; validUntil=1786488292 (~1h). Refresh when expired:
# open gigantti.fi/search in a browser, copy x-algolia-api-key from the z0fl7r8ubh-dsn.algolia.net
# request (DevTools -> Network), and save it to cache/gigantti_key.txt (overrides this constant).
KEY = open(os.path.join(CACHE, "gigantti_key.txt"), encoding="utf-8").read().strip() \
      if os.path.exists(os.path.join(CACHE, "gigantti_key.txt")) else \
      "MWZjMmZjZjc0MzZkN2U2ODM0YTc0Mzg0YjExNTE0M2Q4MDk2ZWE1MGJiYThhZTBkNmIzYzE2NzQyMmJiYWM1NXJlc3RyaWN0SW5kaWNlcz1jb21tZXJjZV8qJTJDY29udGVudF8qJTJDc3RvcmVJbmRleCZ2YWxpZFVudGlsPTE3ODY0ODgyOTI="
APP = "Z0FL7R8UBH"
INDEX = "commerce_b2c_OCFIGIG"

def post(url, payload, headers):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def algolia_search(query, hits_per_page=40, page=0):
    url = f"https://{APP.lower()}-dsn.algolia.net/1/indexes/*/queries"
    payload = {
        "requests": [{
            "indexName": INDEX,
            "params": urllib.parse.urlencode({
                "query": query, "hitsPerPage": hits_per_page, "page": page,
                "facets": [], "filters": ""})
        }]
    }
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "x-algolia-api-key": KEY,
        "x-algolia-application-id": APP,
        "x-algolia-agent": "Algolia for JavaScript (5.56.0); Lite (5.56.0); Browser",
    }
    return post(url, payload, headers)

def main():
    out = {}
    failed = False
    for q in ["mac mini", "mac mini m4 pro", "mac studio"]:
        try:
            d = algolia_search(q)
        except Exception as e:
            print("ERR", q, repr(e)[:120]); failed = True; continue
        try:
            hits = d["results"][0]["hits"]
        except Exception:
            print("unexpected response for", q, str(d)[:200]); continue
        for h in hits:
            title = h.get("title") or h.get("name") or ""
            if not any(k in title.lower() for k in ["mac mini", "mac studio"]):
                continue
            price = h.get("price", {})
            if isinstance(price, dict):
                price = price.get("amount")
            url = h.get("urlB2C") or h.get("productUrl") or ""
            out[h.get("objectID") or title] = {
                "title": title,
                "price": price,
                "availability": h.get("onlineSalesStatus") or "",
                "stockGrade": h.get("stockGrade") or "",
                "storesWithStock": h.get("storesWithStock") or "",
                "presaleDate": h.get("presaleDate") or "",
                "isBuyableOnline": h.get("isBuyableOnline"),
                "url": url,
            }
        time.sleep(0.8)
    if failed and not out:
        print("ALL gigantti queries failed (key expired?) — keeping previous cache; refresh key in cache/gigantti_key.txt")
        return
    with open(os.path.join(CACHE, "gigantti.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for k, v in sorted(out.items(), key=lambda kv: kv[1]["title"]):
        print(f"{v['title'][:70]:70} {v['price']!s:>10}  av={v['availability'][:40]}")

if __name__ == "__main__":
    main()
