# mac-sku-prices — build spec (authoritative)

## Goal (user requirement, verbatim intent)
Build a SIMPLE tool that, in table form:
1. Lists ALL SKUs + common CTO variants of **Mac mini (M3 & M4)** and **Mac Studio (M3 & M4)**.
2. For EACH SKU shows **price + availability** for **every vendor that carries it** — all vendors.
User is asleep; tool must be COMPLETE (built, run, output saved) when they wake. No questions — use judgment.

## Scope decisions (already made — do not revisit)
- **There is NO M3 Mac mini** (Apple jumped M2 -> M4 for Mac mini). So "M3/M4 Mac mini" = **Mac mini M4 + M4 Pro (2024)**. State this in the tool's README.
- Mac Studio "M3 & M4" = **Mac Studio M3 Ultra (2025)** and **Mac Studio M4 Max (2025)**.
- BONUS (same collectors, near-zero cost, more complete): Mac mini M2 / M2 Pro (2023), Mac Studio M2 Max / M2 Ultra (2023) — include as bonus sections only if data comes out of the same fetches; never block the main deliverable on them.
- New/refurb/used all count as "vendors that carry it": new = authorized channels; refurb/used = Back Market, Tori.fi, Huuto.net (label clearly; they are best-effort, may be bot-walled).
- Output: TWO artifacts — `mac_prices.md` (plain markdown tables) and `mac_prices.html` (self-contained, same tables, readable in a browser). Per-model sections. Rows = SKU/config, columns = vendors, cell = price + availability tag. Include a "cheapest" row/summary and an Apple RRP column.

## Project location
`C:\Users\Asad\mac-sku-prices\`
- `spec.md` (this file), `skus.json` (SKU catalog), `vendors/` (one collector module per vendor), `cache/` (JSON per vendor, 24h TTL), `out/mac_prices.md`, `out/mac_prices.html`, `README.md` (what/why/how/limitations), `DONE` marker when finished.

## SKU enumeration (do this FIRST, authoritatively)
1. Apple FI official configurator pages (fetch + parse configs + part numbers + Apple prices):
   - https://www.apple.com/fi/shop/buy-mac/mac-mini
   - https://www.apple.com/fi/shop/buy-mac/mac-studio
   (Apple's JS configurator may need the browser; acceptable to use the catalog pages' JSON or known part numbers. Apple prices = RRP column.)
2. hinta.fi search is the authoritative "what is actually sold in Finland" list — `https://hinta.fi/haku?q=mac+mini` and `...?q=mac+studio` return every tracked product page (server-rendered, /haku?q=, input name "q"). Each product page `https://hinta.fi/<id>` has "Hintavertailu (N kauppaa)" — a SERVER-RENDERED table of sellers: shop name (title="Siirry kauppaan: X"), product name, price, delivery country. Parse rows with regex on `class="hv-oft-tr"` rows: shop via `title="Siirry kauppaan: ([^"]+)"`, price via `hv--price` cell, ship country via `hv--dispatch`.
3. Known part numbers to seed (verify against Apple/hinta.fi):
   - Mac mini M4: 16/256 (MU9D3), 16/512 (MU9E3), 16/1TB, 16/2TB, 24/512 (MCYT4), 24/1TB, 24/2TB, 32/512, 32/1TB, 32/2TB (+32/256 seen on hinta.fi id 4973631)
   - Mac mini M4 Pro: 12c/16c 24/512 (MCX44), 24/1TB, 24/2TB, 48/512, 48/1TB, 48/2TB, 64/1TB, 64/2TB, 64/4TB; 14c/20c 48/512, 48/1TB, 64/1TB, 64/2TB, 64/4TB, 64/8TB
   - Mac Studio M4 Max: 16c/40c 36GB 1TB/2TB/4TB; 20c/48c 64GB 1TB/2TB/4TB; 20c/48c 128GB 1TB/2TB/4TB
   - Mac Studio M3 Ultra: 28c/60c 96GB 1TB/2TB/4TB; 32c/80c 96GB 1TB/2TB/4TB; 32c/80c 192GB 1TB/2TB/4TB (+8TB where offered)
   Build `skus.json` from hinta.fi hits + Apple config pages; label each row M4/M4 Pro/M3 Ultra/M4 Max, chip, CPU/GPU cores, RAM, SSD, part number, family.

## Vendors + fetch strategy (all from live research Aug 2026 — see skill refs for details)
Backbone = hinta.fi (covers: Datatronic, Jimm's, Tietokonekauppa, Proshop, CS Megastore, Data-Systems, Scandinavian Photo, Telia, Elisa, Veikon Kone, Power, Gigantti, Verkkokauppa.com + grey Kasuplan/Cruzbroker) with price + ship country. Then per-vendor availability/price where cheap:

- **Verkkokauppa.com** — JSON API (no auth): search `https://search.service.verkkokauppa.com/fi/api/v1/product-search?filter[q]=<part or name>&sessionId=<any UUID>`; availability `https://product.service.verkkokauppa.com/fi/api/v1/availability?pids=<pid>` (InStock/OutOfStock/LimitedAvailability/SoldOut + flags). REAL stock data.
- **Gigantti** — Algolia (app `Z0FL7R8UBH`, index `commerce_b2c_OCFIGIG`): signed key from `https://www.gigantti.fi/api/algolia/signed-api-key` (browser-only due to Vercel challenge; pass the base64 VERBATIM, never decode). Query `POST https://z0fl7r8ubh-dsn.algolia.net/1/indexes/*/queries` with query "mac mini" / per-part filters; `title`, `price.amount`, stock text, `productUrl`.
- **Power** — Next.js; camofox web_extract renders it, or fetch search page and parse `__NEXT_DATA__`/SSR JSON. Stock words: "Toimitus myymälöistä Click&Collect", "Varastossa".
- **Telia / Elisa** — server-rendered product/search HTML (grep "Mac mini", price, availability text).
- **Veikon Kone** — Magento + Klevu; search results JS-only (browser). Fallback: hinta.fi price.
- **Euronics** — Confirma platform; /fi/haku 404s; must use site's own search box in browser. Fallback: hinta.fi.
- **Multitronic** — server HTML (curl+grep works); category page `https://www.multitronic.fi/tietokoneet-ja-tabletit/poytakoneet/apple-poytakoneet/mac-mini` lists units with prices.
- **Scandinavian Photo** — browser search works (search box -> /hae?q=). M4 16/512, 24/512, M4 Pro 24/512.
- **CS Megastore** — csmegastore.fi, JS shell + search box -> `/l/0/s?sq=<q>`; confirmed carrying full M4/M4 Pro range. (Danish A/S, EUR .fi storefront.)
- **NetOnNet** — netonnet.fi is an SPA shell; netonnet.se (Next.js, same catalog) SSR HTML contains product names+prices — grep `mac mini` there. Label "netonnet.se catalog".
- **Webhallen** — webhallen.com/se/search?searchString=... (JS; browser). SEK prices, ships to FI.
- **Amazon.de** — web_extract/browser on `https://www.amazon.de/s?k=mac+mini+m4` works; "Deliver to Finland", free delivery; parse first-page results + price ("Price, product page" = need product page click; take listed price + "from" offers).
- **Galaxus.de** — web_extract works: `https://www.galaxus.de/search?q=mac+mini+m4` (203 hits, EUR prices listed). Parse product list.
- **Alternate.de** — curl+grep works (`https://www.alternate.de/listing.xhtml?q=mac+mini+m4`) — Mac mini M4/M4 Pro CTO, MAC-System.
- **Computeruniverse.net** — bot-walled (403); try curl_cffi impersonate=chrome; else omit w/ note.
- **Proshop / Data-Systems / Jimm's / Tietokonekauppa / Datatronic / Kuva-Järvinen(no)** — covered by hinta.fi; direct fetch only if cheap. Kuva-Järvinen does NOT carry Mac mini — exclude.
- **Back Market / Tori.fi / Huuto.net** — bot-walled; try browser once each; else "unchecked (bot-walled)" note.
- **Dustin, Prisma, K-Citymarket, Kärkkäinen, Hobby Hall, Rajala, Stockmann, Fotoyks, Elisa?** — Elisa YES; the others do NOT carry Mac mini (verified) — do NOT list them.
- **Apple (apple.fi)** — RRP column from configurator.

## Availability tagging
- Verkkokauppa: real API stock (InStock=Varastossa, LimitedAvailability=Rajoitettu, OutOfStock/SoldOut=Loppu/Myyty).
- Gigantti: Algolia stock field/text ("Saapuu varastoon 2.9.2026" = backorder date; "2 kpl saatavilla verkkokaupasta" = stock).
- Others: parse for stock words (Varastossa / Heti varastosta / Toimitus X pv / Tilaustuote / Loppuunmyyty / Saapuu varastoon / Ei varastossa); else "—".
- Never fabricate stock: if unparseable, leave "—" with a footnote "availability not machine-readable".

## Engineering rules
- Python 3.11 (`python` on this Windows box = 3.11.15; uv available; `pip` may target 3.12 — use `python -m pip` or uv). If needed: `python -m pip install curl_cffi requests beautifulsoup4`.
- One collector module per vendor in `vendors/`, each returns {sku_id or name-match: {price, availability, source_url, fetched_at}}; normalize prices to float + "1 219 €" display.
- SKU matching: match on part number (MU9D3...) OR normalized name (lowercase, strip: "mac mini m4 16 gb 512 gb"). Fuzzy tolerance; report unmatched SKUs per vendor in a WARNINGS section.
- Sleep 0.5–1 s between requests; retry 2x with backoff on 5xx/timeouts; hard per-vendor timeout.
- Cache raw vendor JSON in cache/ (24h TTL) so re-runs are fast.
- Bot walls: try plain curl w/ Chrome UA -> curl_cffi impersonate="chrome" -> camofox via web_extract (hermes_tools.web_extract works in cron: `from hermes_tools import web_extract`) -> browser fallback. Never loop a walled site more than 2 attempts.
- Read-only: NO purchases, no logins, no form submissions beyond search boxes.

## Verification before DONE
1. Every SKU in skus.json has >=1 vendor price (Apple RRP always present; hinta.fi usually covers).
2. Spot-check 5 SKUs: fetch 1-2 live vendor pages and confirm price matches the table.
3. Tables render: open out/mac_prices.html exists and contains all sections; md tables well-formed.
4. Write DONE + a build summary (SKUs count, vendors covered, per-vendor success/fail, warnings).
5. Notify: BurntToast works on this box — `powershell -Command "New-BurntToastNotification -Text 'Mac SKU price tool DONE','out/mac_prices.html ready'"` (or fallback: write a plain text file C:\Users\Asad\mac-sku-prices\DONE).

## Skill references to load (they contain the recon detail)
- skill `finnish-tech-retailers` → references/finland-retailer-list.md (vendor list, hinta.fi method, Apple section) + references/verkkokauppa-com-api.md (JSON API + availability + CLI).
- skill `web-api-reconnaissance` → references/algolia-storefront-recon.md (Gigantti Algolia app/index/key caveat).
