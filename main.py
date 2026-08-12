#!/usr/bin/env python3
"""mac-sku-prices: SKU x vendor price/availability tables for Mac mini (M4/M4 Pro) and Mac Studio (M3 Ultra/M4 Max).

Merges cache/*.json (collected by vendors/*.py collectors) into per-family tables.
Re-run: python main.py  (uses cache; refresh cache by re-running the collectors).
Output: out/mac_prices.md + out/mac_prices.html
"""
import json, os, re, sys, html

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
OUT = os.path.join(BASE, "out")
os.makedirs(OUT, exist_ok=True)

def load(name):
    p = os.path.join(CACHE, name)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return None

# ---------------- vendor registry ----------------
# name: (display name, source type)
VENDORS = [
    ("apple",     "Apple (apple.fi)"),
    ("verkkokauppa", "Verkkokauppa.com"),
    ("gigantti",  "Gigantti"),
    ("power",     "Power"),
    ("telia",     "Telia"),
    ("elisa",     "Elisa"),
    ("veikonkone","Veikon Kone"),
    ("euronics",  "Euronics"),
    ("multitronic","Multitronic"),
    ("datatronic","Datatronic"),
    ("jimms",     "Jimm's PC-store"),
    ("tietokonekauppa", "Tietokonekauppa"),
    ("proshop",   "Proshop (DK)"),
    ("datasystems","Data-Systems"),
    ("scandinavianphoto", "Scandinavian Photo"),
    ("csmegastore", "CS Megastore"),
    ("netonnet",  "NetOnNet"),
    ("webhallen", "Webhallen (SE)"),
    ("amazon",    "Amazon.de"),
    ("galaxus",   "Galaxus (DE)"),
    ("alternate", "Alternate (DE)"),
    ("computeruniverse", "Computeruniverse (DE)"),
    ("backmarket","Back Market (refurb)"),
    ("tori",      "Tori.fi (used)"),
    ("huuto",     "Huuto.net (used)"),
    ("grey",      "hinta.fi grey (Kasuplan/Cruzbroker)"),
]

# ---------------- SKU / name helpers ----------------
def norm(s):
    return re.sub(r"\s+", " ", s.lower().replace("\u00a0", " "))

RAM_SET = {8, 16, 24, 32, 36, 48, 64, 96, 128, 192, 256}
SSD_SET = {256, 512, 1024, 2048, 4096, 8192, 16384}

def parse_ram_ssd(title):
    """Extract (ram_gb, ssd_gb) from a product title. Priority: explicit RAM/SSD labels,
    then slash patterns (16/256, 24 Gt/512 Gt, 96/1TB, 256GB RAM/16TB), then unit tokens."""
    t = norm(title)
    ram = ssd = None
    # 1) explicit labels
    m = re.search(r"(\d{1,4})\s*(?:gt|gb)\s*(?:ram|muisti|yhteismuisti)", t)
    if m: ram = int(m.group(1))
    m = re.search(r"(\d{1,5})\s*((?:gt|gb|tt|tb))\s*(?:ssd|levy|tallennustila|hårddisk)", t)
    if m: ssd = int(m.group(1)) * (1024 if m.group(2) in ("tt", "tb") else 1)
    # 2) slash patterns (validate against known RAM/SSD values so "m4/24/512" skips the chip digit)
    if ram is None or ssd is None:
        RAM_V = (8, 16, 24, 32, 36, 48, 64, 96, 128, 192, 256)
        SSD_V = (256, 512, 1024, 2048, 4096, 8192, 16384)
        pat = re.compile(r"(\d{1,3})\s*(?:gt|gb|ram)?\s*/\s*(\d{1,5})\s*((?:gt|gb|tt|tb))?\s*(?:ssd)?")
        pos = 0
        while pos < len(t):
            m = pat.search(t, pos)
            if not m:
                break
            g1, g2, u2 = int(m.group(1)), int(m.group(2)), (m.group(3) or "")
            s2 = g2 * 1024 if u2.startswith(("tt", "tb")) else g2
            if g1 in RAM_V and s2 in SSD_V:
                ram = g1
                ssd = s2
                break
            pos = m.start() + 1
    # 3) unit tokens (SSD-first order like Galaxus)
    if ram is None or ssd is None:
        tokens = []
        for mm in re.finditer(r"(\d{1,5})\s*(gt|gb|tt|tb)", t):
            val = int(mm.group(1))
            if mm.group(2) in ("tt", "tb"):
                val *= 1024
            tokens.append(val)
        for val in tokens:
            if ram is None and val in RAM_SET and val not in SSD_SET:
                ram = val
        for val in reversed(tokens):
            if ssd is None and val in SSD_SET:
                ssd = val
        # ambiguous 256: assign to RAM if title suggests RAM (e.g. "256GB RAM/16TB")
        if ram is None and 256 in tokens and "ram" in t:
            ram = 256
    return ram, ssd

def chip_of(title):
    t = norm(title)
    if "m4 pro" in t: return "m4pro"
    if "m4 max" in t: return "m4max"
    if "m3 ultra" in t: return "m3ultra"
    if "m2 ultra" in t: return "m2ultra"
    if "m2 max" in t: return "m2max"
    if "m2" in t: return "m2"
    if "m4" in t: return "m4"
    return None

def family_of(chip):
    return {
        "m4": "Mac mini M4 (2024)",
        "m4pro": "Mac mini M4 Pro (2024)",
        "m4max": "Mac Studio M4 Max (2025)",
        "m3ultra": "Mac Studio M3 Ultra (2025)",
        "m2": "Mac mini M2 (2023, bonus)",
        "m2max": "Mac Studio M2 (2023, bonus)",
        "m2ultra": "Mac Studio M2 (2023, bonus)",
    }.get(chip)

def cores_of(title):
    t = norm(title)
    mc = re.findall(r"(\d{1,2})[- ]?(?:c|core)", t)
    # prefer CPU core count like 12c/14c/28c/32c (first match) and GPU 16c/20c/60c/80c (second)
    if len(mc) >= 2:
        return int(mc[0]), int(mc[1])
    return None

# ---------------- hintafi backbone ----------------
def load_hintafi():
    d = load("hintafi_products.json")
    if not d: return {}
    # page id -> (fam, ram, ssd) from skus.json for config inheritance
    skus = json.load(open(os.path.join(BASE, "skus.json"), encoding="utf-8"))
    page_cfg = {}
    for fam_name, fam in skus["families"].items():
        for s in fam["skus"]:
            if s.get("hintafi"):
                page_cfg[str(s["hintafi"])] = (fam_name, s["ram"], s["ssd"])
    out = {}
    for pid, page in d.items():
        pcfg = page_cfg.get(str(pid))
        for r in page.get("rows", []):
            if not r.get("price"): continue
            shop = (r["shop"] or "grey").strip()
            cfg = r.get("product") or page.get("title", "")
            ram, ssd = parse_ram_ssd(cfg)
            chip = chip_of(cfg)
            fam = family_of(chip) if chip else None
            if pcfg:
                fam = fam or pcfg[0]
                ram = ram or pcfg[1]
                ssd = ssd or pcfg[2]
            if fam is None or ram is None or ssd is None:
                continue
            key = (fam, ram, ssd)
            out.setdefault(key, []).append({
                "vendor": shop, "price": float(r["price"]),
                "availability": r.get("delivery", ""), "country": r.get("country", ""),
                "src": f"hinta.fi/{pid}", "title": cfg,
            })
    return out

# ---------------- generic vendor item loader ----------------
def vendor_items():
    """Returns dict vendor_key -> list of items with parsed (fam, ram, ssd)."""
    res = {}
    def add(vk, items, country=""):
        for it in items or []:
            t = it.get("title") or ""
            if not t: continue
            # alternate.de keeps RAM/SSD in a "spec" field ("24 GB Arbeitsspeicher | 512 GB SSD")
            parse_t = t + " " + (it.get("spec") or "")
            chip = chip_of(t)
            if chip is None: continue
            if "mac mini" not in norm(t) and "mac studio" not in norm(t): continue
            # M2 family routing: mini vs studio
            if chip in ("m2", "m2max", "m2ultra"):
                if "mac studio" in norm(t):
                    chip = "m2max" if "max" in norm(t) else ("m2ultra" if "ultra" in norm(t) else "m2")
                else:
                    chip = "m2"
            fam = family_of(chip)
            ram, ssd = parse_ram_ssd(parse_t)
            if ram is None or ssd is None: continue
            price = it.get("price")
            if it.get("price_eur") is not None:
                price = it["price_eur"]
            res.setdefault(vk, []).append({
                "fam": fam, "ram": ram, "ssd": ssd, "title": t,
                "price": price, "availability": it.get("availability") or "",
                "url": it.get("url") or "", "country": country,
            })

    # verkkokauppa (from API cache)
    vk = load("verkkokauppa.json")
    if vk:
        for pid, it in vk.items():
            if not it.get("name") or pid == "?": continue
            t = it["name"]
            if "mac mini" not in norm(t) and "mac studio" not in norm(t): continue
            chip = chip_of(t)
            if chip is None: continue
            ram, ssd = parse_ram_ssd(t)
            if ram is None or ssd is None: continue
            av = it.get("availability") or ""
            avmap = {"InStock": "Varastossa", "LimitedAvailability": "Rajoitettu saatavuus",
                     "SoldOut": "Loppu", "OnlineOnly": "Vain verkossa"}
            av = avmap.get(av, av)
            res.setdefault("verkkokauppa", []).append({
                "fam": family_of(chip), "ram": ram, "ssd": ssd, "title": t,
                "price": it.get("price_float") or it.get("price"), "availability": av,
                "url": it.get("url") or "", "country": "Suomi",
            })

    # gigantti (Algolia cache)
    g = load("gigantti.json")
    if g:
        for oid, it in g.items():
            t = it.get("title") or ""
            if not t: continue
            chip = chip_of(t)
            if chip is None: continue
            if "mac mini" not in norm(t) and "mac studio" not in norm(t): continue
            ram, ssd = parse_ram_ssd(t)
            if ram is None or ssd is None: continue
            av = "Ostettavissa verkossa" if it.get("isBuyableOnline") else ""
            if it.get("presaleDate"): av += " (presale " + it["presaleDate"][:10] + ")"
            res.setdefault("gigantti", []).append({
                "fam": family_of(chip), "ram": ram, "ssd": ssd, "title": t,
                "price": it.get("price"), "availability": av.strip(),
                "url": it.get("url") or "", "country": "Suomi",
            })

    # vendor_*.json caches
    for vk_name, disp, *rest in [
        ("power", None), ("multitronic", None), ("alternate", None), ("galaxus", None),
        ("amazon", None), ("webhallen", None), ("csmegastore", None),
        ("scandinavianphoto", None), ("veikonkone", None), ("euronics", None),
        ("netonnet", None), ("telia", None), ("elisa", None),
    ]:
        d = load(f"vendor_{vk_name}.json")
        if not d: continue
        items = d.get("items") or []
        country = {"webhallen": "SE", "amazon": "DE", "galaxus": "DE", "alternate": "DE",
                   "netonnet": "SE"}.get(vk_name, "Suomi")
        add(vk_name, items, country)
    return res

# ---------------- build table ----------------
def fmt_price(p):
    if p is None: return "—"
    try:
        v = float(p)
    except (TypeError, ValueError):
        return str(p)
    if v == int(v):
        return f"{int(v):,} €".replace(",", " ")
    return f"{v:,.2f} €".replace(",", " ")

def main():
    skus = json.load(open(os.path.join(BASE, "skus.json"), encoding="utf-8"))
    hintafi = load_hintafi()
    vitems = vendor_items()

    families = skus["families"]
    # vendor keys present in data
    active = sorted({k for k, v in vitems.items() if v})
    # show hintafi-derived vendors as columns too
    hf_vendors = sorted({r["vendor"] for rows in hintafi.values() for r in rows})
    # map hintafi shop names to columns
    SHOP_MAP = {
        "Verkkokauppa.com": "verkkokauppa", "Gigantti": "gigantti", "Power.fi": "power",
        "Telia": "telia", "Elisan Verkkokauppa": "elisa", "Veikon Kone": "veikonkone",
        "Multitronic": "multitronic", "Datatronic": "datatronic", "Jimm's PC-store": "jimms",
        "Tietokonekauppa.fi": "tietokonekauppa", "Proshop": "proshop",
        "Data-Systems": "datasystems", "Scandinavian Photo": "scandinavianphoto",
        "CS MEGASTORE": "csmegastore", "NetOnNet": "netonnet",
    }
    columns = ["apple"]
    for vk in active:
        if vk not in columns: columns.append(vk)
    for v in hf_vendors:
        c = SHOP_MAP.get(v, "grey")
        if c not in columns: columns.append(c)
    # order: domestic first
    order = ["apple", "verkkokauppa", "gigantti", "power", "telia", "elisa", "veikonkone",
             "euronics", "multitronic", "datatronic", "jimms", "tietokonekauppa", "proshop",
             "datasystems", "scandinavianphoto", "csmegastore", "netonnet", "webhallen",
             "amazon", "galaxus", "alternate", "computeruniverse", "backmarket", "tori",
             "huuto", "grey"]
    columns = [c for c in order if c in columns]

    disp = dict((vk, d) for vk, d, *_ in [(v[0], v[1]) for v in VENDORS])
    disp["grey"] = "hinta.fi grey (Kasuplan/Cruzbroker)"
    disp["hinta.fi-muu"] = "hinta.fi-muu"

    # collect per-SKU cell data
    def price_avail(sku, vk):
        """Return (price_float|None, availability_str|None, multi_offers_bool)."""
        fam, ram, ssd = sku["fam"], sku["ram"], sku["ssd"]
        if vk == "apple":
            return (sku.get("apple"), "RRP", False)
        if vk in vitems:
            cands = [it for it in vitems[vk] if it["fam"] == fam and it["ram"] == ram and it["ssd"] == ssd]
            if cands:
                priced = [c for c in cands if isinstance(c.get("price"), (int, float))]
                if priced:
                    it = min(priced, key=lambda c: c["price"])
                    return (float(it["price"]), it.get("availability") or "", len(priced) > 1)
                return (None, cands[0].get("availability") or "", False)
        for r in hintafi.get((fam, ram, ssd), []):
            if SHOP_MAP.get(r["vendor"]) == vk or (vk == "grey" and r["vendor"] not in SHOP_MAP):
                av = r.get("availability") or ""
                cnt = r.get("country") or ""
                extra = av + (f" ({cnt})" if cnt else "")
                return (float(r["price"]), extra, False)
        return (None, None, False)

    def cell_for(sku, vk):
        p, av, multi = price_avail(sku, vk)
        if p is None and not av:
            return None
        s = ("alk. " if multi else "") + (fmt_price(p) if p is not None else "?")
        return (s + (f" · {av}" if av else "")).strip()

    def cheapest(fam, ram, ssd):
        best = None
        for vk in columns:
            p, av, _ = price_avail({"fam": fam, "ram": ram, "ssd": ssd, "apple": None}, vk)
            if p is None:
                continue
            if best is None or p < best[0]:
                best = (p, vk)
        return best

    def short_chip(name):
        for c in ["M4 Pro", "M3 Ultra", "M4 Max", "M2 Ultra", "M2 Max"]:
            if c in name:
                return c
        if "M2" in name:
            return "M2"
        if "M4" in name:
            return "M4"
        return ""

    # ---------------- render: markdown ----------------
    md_lines = []

    md_lines.append("# Mac mini / Mac Studio — SKU x Vendor price & availability (Finland)")
    md_lines.append("")
    md_lines.append(f"*Generated {skus['generated']} (prices EUR incl. VAT). Data: Apple FI configurator (RRP), "
                    "Verkkokauppa.com API (live stock), Gigantti Algolia, hinta.fi seller tables, and each "
                    "store's own site (see README for per-vendor sources).*")
    md_lines.append("")
    md_lines.append("**Vendors:** " + "; ".join(f"{disp[c]}" for c in columns))
    md_lines.append("")
    md_lines.append("Availability tags: `Varastossa`=in stock, `Rajoitettu`=limited, `Loppu`=out, "
                    "`Tilaustuote`=made-to-order, delivery estimates in days (pv). `—` = not carried / no data.")
    md_lines.append("")

    for fam_name, fam in families.items():
        md_lines.append(f"## {fam_name} — {fam.get('chip','')}")
        md_lines.append("")
        md_lines.append("| Config | " + " | ".join(disp[c] for c in columns) + " | Cheapest |")
        md_lines.append("|" + "---|" * (len(columns) + 2))
        for s in fam["skus"]:
            sv = dict(s, fam=fam_name)
            row = [f"**{s['name']}**"]
            for c in columns:
                cell = cell_for(sv, c)
                row.append(cell if cell else "—")
            ch = cheapest(fam_name, s["ram"], s["ssd"])
            row.append(f"**{fmt_price(ch[0])}** ({disp[ch[1]]})" if ch else "—")
            md_lines.append("| " + " | ".join(row) + " |")
        md_lines.append("")

    md = "\n".join(md_lines)
    open(os.path.join(OUT, "mac_prices.md"), "w", encoding="utf-8").write(md)

    # ---------------- render: interactive HTML ----------------
    rows_data = []
    for fam_name, fam in families.items():
        ftype = "Mac mini" if "Mac mini" in fam_name else "Mac Studio"
        chip_full = fam.get("chip", "")
        for s in fam["skus"]:
            sv = dict(s, fam=fam_name)
            m = re.search(r"(\d{1,2})C/(\d{1,2})C", s["name"])
            cpu = gpu = None
            if m:
                cpu, gpu = int(m.group(1)), int(m.group(2))
            if cpu is None:
                m = re.search(r"(\d{1,2})\s*C\s*CPU", chip_full, re.I)
                if m: cpu = int(m.group(1))
                m = re.search(r"(\d{1,2})\s*C\s*GPU", chip_full, re.I)
                if m: gpu = int(m.group(1))
            vendors = {}
            for c in columns:
                p, av, multi = price_avail(sv, c)
                if p is not None or av:
                    vendors[c] = {"p": p, "a": av or "", "m": multi}
            ch = cheapest(fam_name, s["ram"], s["ssd"])
            rows_data.append({
                "name": s["name"], "type": ftype, "chip_full": chip_full,
                "cpu": cpu, "gpu": gpu, "ram": s["ram"], "ssd": s["ssd"],
                "part": s.get("part"), "family": fam_name,
                "apple": s.get("apple"),
                "halvin": {"v": ch[1], "p": ch[0], "d": disp[ch[1]]} if ch else None,
                "vendors": vendors,
            })

    vendors_out = [[c, disp[c]] for c in columns]
    meta_out = {"generated": skus["generated"],
                "src": "Apple FI (RRP), Verkkokauppa.com API (live stock), Gigantti Algolia, hinta.fi, "
                       "and each store's own site. Availability dots: green=in stock, yellow=limited, "
                       "red=out of stock / made to order. — = not carried or unknown."}
    tpl = open(os.path.join(BASE, "assets", "frontend.html"), encoding="utf-8").read()
    html_doc = (tpl
                .replace("__DATA__", json.dumps(rows_data, ensure_ascii=False))
                .replace("__VENDORS__", json.dumps(vendors_out, ensure_ascii=False))
                .replace("__META__", json.dumps(meta_out, ensure_ascii=False)))
    open(os.path.join(OUT, "mac_prices.html"), "w", encoding="utf-8").write(html_doc)

    print("Wrote out/mac_prices.md + out/mac_prices.html")
    print("Columns:", len(columns), "| Families:", len(families), "| SKUs:", sum(len(f["skus"]) for f in families.values()))
    print("Vendor item counts:", {k: len(v) for k, v in sorted(vitems.items())})
    print("hintafi keys:", len(hintafi))

if __name__ == "__main__":
    main()
