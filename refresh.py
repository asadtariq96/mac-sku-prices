#!/usr/bin/env python3
"""refresh.py — auto-refresh pipeline for mac-sku-prices.

Runs the automatic collectors (APIs + server-rendered sites), re-fetches the
hinta.fi backbone, and rebuilds out/mac_prices.md + .html.

Does NOT cover the pure-browser stores (Veikon Kone, Euronics, CS Megastore,
Scandinavian Photo, Amazon.de, Webhallen) — those snapshots live in
cache/vendor_*.json and are re-captured by the weekly cron agent (or manually
via their site search boxes). See README.md.

Usage: python refresh.py
"""
import json, os, re, subprocess, sys, time, urllib.request, urllib.parse, html

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

def run(script):
    print(f"\n=== {script} ===")
    r = subprocess.run([sys.executable, os.path.join(BASE, "vendors", script)],
                       cwd=BASE, capture_output=True, text=True, timeout=600)
    print(r.stdout[-1500:])
    if r.returncode != 0:
        print("WARN: non-zero exit", r.returncode, r.stderr[-500:])

def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def refresh_hintafi():
    """Re-fetch every tracked hinta.fi product page + its seller table (the price backbone)."""
    print("\n=== hinta.fi backbone ===")
    skus = json.load(open(os.path.join(BASE, "skus.json"), encoding="utf-8"))
    ids = []
    for fam in skus["families"].values():
        for s in fam["skus"]:
            if s.get("hintafi"):
                ids.append(str(s["hintafi"]))
    ids = sorted(set(ids))
    print("product pages:", len(ids))
    data = {}
    for pid in ids:
        try:
            body = get(f"https://hinta.fi/{pid}")
            mh = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
            title = re.sub(r"<[^>]+>", "", json.loads('"' + mh.group(1).replace('"', '\\"') + '"')) if mh else ""
            rows = []
            for m in re.finditer(r'<tr class="hv-oft-tr">(.*?)</tr>', body, re.S):
                seg = m.group(1)
                shop = re.search(r'title="Siirry kauppaan: ([^"]+)"', seg)
                shop = html.unescape(shop.group(1)) if shop else "grey"
                prod = re.search(r'class="[^"]*hv--product[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>', seg, re.S)
                prod = html.unescape(prod.group(1)).strip() if prod else ""
                price = re.search(r'class="[^"]*hv--price[^"]*"[^>]*>\s*<strong>([\d\s.,]+)\s*€', seg, re.S)
                price = re.sub(r"\s", "", price.group(1)).replace(",", ".") if price else ""
                deliv = re.search(r'class="[^"]*hv--delivery-time[^"]*"[^>]*>([^<]+)</td>', seg, re.S)
                deliv = deliv.group(1).strip() if deliv else ""
                country = re.search(r'title="Lähetysmaa: ([^"]+)"', seg)
                country = country.group(1) if country else ""
                rows.append({"shop": shop, "product": prod, "price": price,
                             "delivery": deliv, "country": country})
            data[pid] = {"id": pid, "title": title, "rows": rows}
            time.sleep(0.6)
        except Exception as e:
            print("  ERR", pid, repr(e)[:80])
    # merge with previously captured pages not in skus.json (generic studio pages etc.)
    old = os.path.join(CACHE, "hintafi_products.json")
    if os.path.exists(old):
        prev = json.load(open(old, encoding="utf-8"))
        for pid, page in prev.items():
            if pid not in data:
                data[pid] = page
    with open(old, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("hintafi cached:", len(data), "pages")

def main():
    t0 = time.time()
    refresh_hintafi()
    run("verkkokauppa.py")
    run("gigantti.py")      # uses cached signed key; may be expired -> keeps old cache if key rejected
    run("curl_batch.py")    # multitronic, netonnet, galaxus(403 fallback), alternate stub
    run("alternate.py")
    print("\n=== rebuild ===")
    r = subprocess.run([sys.executable, os.path.join(BASE, "main.py")],
                       cwd=BASE, capture_output=True, text=True, timeout=300)
    print(r.stdout[-800:])
    if r.returncode != 0:
        print("REBUILD FAILED:", r.stderr[-800:])
        sys.exit(1)
    print(f"\nrefresh done in {time.time()-t0:.0f}s — out/mac_prices.md + .html updated")
    print("NOTE: browser-only stores (Veikon Kone, Euronics, CS Megastore, Scandinavian Photo,")
    print("      Amazon.de, Webhallen) use cached snapshots; cron agent re-captures them weekly.")

if __name__ == "__main__":
    main()
