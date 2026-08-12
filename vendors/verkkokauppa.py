#!/usr/bin/env python3
"""Verkkokauppa.com collector: search + availability JSON APIs."""
import json, os, sys, time, uuid, urllib.request, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CACHE = os.path.join(os.path.dirname(__file__), "..", "cache")
os.makedirs(CACHE, exist_ok=True)

def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def search(q, size=24):
    sid = str(uuid.uuid4())
    url = "https://search.service.verkkokauppa.com/fi/api/v1/product-search" + "?" + urllib.parse.urlencode({
        "page[size]": size, "filter[q]": q, "sessionId": sid})
    return get(url)

def availability(pids):
    if not pids: return {}
    url = "https://product.service.verkkokauppa.com/fi/api/v1/availability?pids=" + ",".join(pids)
    try:
        return get(url)
    except Exception:
        return {}

def main():
    queries = ["mac mini", "mac studio"]
    out = {}
    for q in queries:
        try:
            d = search(q)
        except Exception as e:
            print("SEARCH ERR", q, e); continue
        prods = d.get("data", [])
        pids = []
        for p in prods:
            pid = p.get("id")
            if pid: pids.append(pid)
            out[pid or "?"] = {
                "name": (p.get("attributes", {}).get("name") or "").strip(),
                "price": (p.get("attributes", {}).get("articles", [{}])[0].get("price", {}) or {}).get("currentFormatted"),
                "price_float": (p.get("attributes", {}).get("articles", [{}])[0].get("price", {}) or {}).get("current"),
                "url": p.get("links", {}).get("self"),
                "query": q,
            }
        av = availability(pids)
        avmap = {}
        if isinstance(av, list):
            for a in av:
                if isinstance(a, dict):
                    avmap[str(a.get("pid"))] = a
        for pid, info in out.items():
            if pid in avmap:
                a = avmap[pid]
                status = a.get("status", {})
                info["availability"] = status.get("schema")
                info["availability_og"] = status.get("og")
                sh = a.get("stocks", {}).get("shipment", {})
                info["stock"] = sh.get("stock")
                info["stock_status"] = sh.get("stockStatus")
                info["eta"] = (sh.get("minEstimate"), sh.get("maxEstimate"))
        time.sleep(0.5)
    with open(os.path.join(CACHE, "verkkokauppa.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for pid, info in sorted(out.items(), key=lambda kv: kv[1]["name"]):
        if info.get("name"):
            print(f"{info['name'][:70]:70} {info.get('price') or '?':>10}  av={info.get('availability','?'):20} stock={info.get('stock_count')}")

if __name__ == "__main__":
    main()
