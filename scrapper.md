# Saflow Google-Maps Foreign-Client Scraper

A Python pipeline that finds potential foreign clients for **Saflow Advertising** by mining Google Maps in **Dubai, the Americas, and Europe**, then enriches each business with an email scraped from its own website. Results land in a local Postgres database, ready for cold-outreach campaigns.

> 📂 Code lives in [`./scrapper/`](./scrapper). This file is the top-level spec and operator manual.

---

## 1. Overview & Goal

**Who it's for.** Saflow's BD/sales side. The agency runs performance marketing, SEO, creative production and analytics for brands in 14+ countries (USA, UK, Germany, UAE, Australia, Canada, Singapore, Netherlands, France, India and more) — but its inbound lists are too small to feed the funnel. This tool builds those lists.

**What it does.** Two-stage pipeline:

1. **Discovery.** A Playwright-driven scraper feeds queries like `"boutique hotel in Dubai"` or `"D2C brand in Berlin"` into Google Maps, scrolls all results, and extracts each business's name, address, phone, website, category, rating, reviews count, lat/lng, and Google `place_id`.
2. **Enrichment.** For every business that has a website, an httpx + BeautifulSoup crawler visits the home page and common contact pages (`/contact`, `/about`, `/team`) and extracts emails (with role-based detection — `info@`, `hello@` are flagged) and social-media links.

**Where the data lands.** Local Postgres 16 (via Docker). Four tables: `businesses`, `search_queries`, `contacts`, `scrape_runs`. CSV export available.

**Primary outcome.** A queryable lead database with **email as the top-priority field**, phone as secondary, tagged by country and ICP vertical.

---

## 2. ⚠️ Legal & ToS notice

Direct scraping of Google Maps violates Google's Terms of Service. This tool is provided for educational / internal-use purposes. Risks:

- **Account / IP bans** from Google if rate limits are exceeded or stealth fails.
- **Litigation exposure** in some jurisdictions (notably the EU under the DSM Directive). Public, factual business data is generally lower-risk than scraping reviews or photos.
- **Captcha walls** that pause the scraper indefinitely.

**Mitigations baked into the design:**

- `playwright-stealth` to evade simple bot fingerprinting.
- Random delays between actions (uniform 2–7s, configurable in `.env`).
- Rotating user-agent strings from a built-in pool.
- A `HTTP_PROXY` env var that, when set, routes all browser traffic through your proxy. **Recommended for any run >100 queries** — buy residential proxies (Bright Data, Smartproxy) for production.
- Captcha detection: when Google shows a captcha, the scraper stops and writes the offending query back to `search_queries` with `status='blocked'` so it can be retried after cooldown.

**Production-grade alternative.** Switch to the [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service/overview) at ~USD 17 per 1k detail requests. The schema and CLI in this tool are designed to support that swap — the discovery module would change but the rest of the pipeline is unaffected.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                          CLI (Typer)                          │
│                                                                │
│   init        queries:gen     scrape       enrich     export  │
└────┬──────────────┬──────────────┬─────────────┬──────────────┘
     │              │              │             │
     ▼              ▼              ▼             ▼
 ┌─────────┐  ┌──────────┐  ┌──────────────┐  ┌─────────┐
 │ Alembic │  │  Query   │  │  Discovery   │  │ Enrich- │
 │ migrate │  │ generator│  │  Playwright  │  │  ment   │
 │         │  │  cities  │  │  + stealth   │  │ httpx + │
 │         │  │  × verts │  │              │  │  BS4    │
 └────┬────┘  └────┬─────┘  └──────┬───────┘  └────┬────┘
      │            │               │                │
      └────────────┴───────────────┴────────────────┘
                          │
                          ▼
                ┌──────────────────────┐
                │  Postgres 16 (local) │
                │  businesses          │
                │  search_queries      │
                │  contacts            │
                │  scrape_runs         │
                └──────────────────────┘
                          │
                          ▼
                ┌──────────────────────┐
                │  leads.csv (export)  │
                └──────────────────────┘
```

---

## 4. Folder layout

```
scrapper/
├── README.md                       short pointer back to /scrapper.md
├── docker-compose.yml              Postgres 16 + Adminer
├── .env.example                    env-var template
├── .gitignore
├── pyproject.toml                  installable as `scrapper` package
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/                   auto-generated migrations
├── db/
│   ├── schema.sql                  canonical DDL (run-anywhere fallback)
│   └── seeds/
│       ├── cities.csv              target cities by country
│       └── verticals.csv           vertical seed keywords
├── src/scrapper/
│   ├── __init__.py
│   ├── config.py                   Pydantic Settings from .env
│   ├── db.py                       SQLAlchemy engine + session
│   ├── models.py                   ORM models (Business, SearchQuery, Contact, ScrapeRun)
│   ├── queries.py                  generate cities × verticals queue
│   ├── cli.py                      Typer CLI entrypoint
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── maps.py                 Playwright Google Maps scraper
│   │   ├── selectors.py            centralised CSS/aria selectors
│   │   └── parsers.py              detail-panel parsers
│   ├── enrichment/
│   │   ├── __init__.py
│   │   ├── website.py              httpx fetcher with retries
│   │   └── extractor.py            email + social regex / heuristics
│   └── exporters/
│       ├── __init__.py
│       └── csv.py
└── tests/
    ├── __init__.py
    └── test_extractor.py
```

---

## 5. Quickstart

```bash
# 1. Bring up Postgres + Adminer
cd scrapper
docker compose up -d postgres adminer
# Postgres: localhost:5432   Adminer UI: http://localhost:8080  (server=postgres, user=saflow, pass=saflow, db=scrapper)

# 2. Install Python deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium       # ~170MB browser binary

# 3. Configure
cp .env.example .env               # then edit if you need a proxy or different DB password

# 4. Init schema (creates 4 tables)
python -m scrapper.cli init

# 5. Generate ~2k search queries (cities × verticals)
python -m scrapper.cli queries:gen

# 6. Run discovery on the first 25 queries
python -m scrapper.cli scrape --limit 25

# 7. Enrich businesses with websites (find their emails)
python -m scrapper.cli enrich --limit 200

# 8. Export to CSV
python -m scrapper.cli export --out leads.csv

# 9. See current counts
python -m scrapper.cli stats
```

---

## 6. Database schema

Canonical DDL also at `scrapper/db/schema.sql`.

```sql
CREATE TABLE search_queries (
  id              BIGSERIAL PRIMARY KEY,
  query_text      TEXT NOT NULL,
  country         TEXT NOT NULL,                -- ISO-3166 alpha-2 (e.g. 'AE','US')
  city            TEXT,
  vertical        TEXT,                         -- ecommerce | hospitality | professional | b2b
  category        TEXT,                         -- raw seed keyword
  status          TEXT NOT NULL DEFAULT 'pending', -- pending | running | done | failed | blocked
  last_run_at     TIMESTAMPTZ,
  results_count   INTEGER NOT NULL DEFAULT 0,
  notes           TEXT,
  UNIQUE (query_text, city, country)
);
CREATE INDEX idx_search_queries_status ON search_queries(status);

CREATE TABLE businesses (
  id                  BIGSERIAL PRIMARY KEY,
  place_id            TEXT UNIQUE NOT NULL,
  name                TEXT NOT NULL,
  category            TEXT,
  address             TEXT,
  city                TEXT,
  region              TEXT,
  country             TEXT NOT NULL,
  postal_code         TEXT,
  phone               TEXT,
  website             TEXT,
  rating              NUMERIC(2,1),
  reviews_count       INTEGER,
  lat                 NUMERIC(9,6),
  lng                 NUMERIC(9,6),
  google_url          TEXT,
  vertical            TEXT,
  source_query_id     BIGINT REFERENCES search_queries(id) ON DELETE SET NULL,
  first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_scraped_at     TIMESTAMPTZ,
  enrichment_status   TEXT NOT NULL DEFAULT 'pending', -- pending | done | failed | skipped
  enriched_at         TIMESTAMPTZ
);
CREATE INDEX idx_businesses_country ON businesses(country);
CREATE INDEX idx_businesses_vertical ON businesses(vertical);
CREATE INDEX idx_businesses_enrichment_status ON businesses(enrichment_status);

CREATE TABLE contacts (
  id              BIGSERIAL PRIMARY KEY,
  business_id     BIGINT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  kind            TEXT NOT NULL,                -- email | phone | linkedin | instagram | facebook | twitter
  value           TEXT NOT NULL,
  source_url      TEXT,
  confidence      NUMERIC(3,2),
  is_role_based   BOOLEAN NOT NULL DEFAULT FALSE,
  found_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (business_id, kind, value)
);
CREATE INDEX idx_contacts_business_id ON contacts(business_id);
CREATE INDEX idx_contacts_kind ON contacts(kind);

CREATE TABLE scrape_runs (
  id              BIGSERIAL PRIMARY KEY,
  started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at        TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'running',
  query_count     INTEGER NOT NULL DEFAULT 0,
  results_count   INTEGER NOT NULL DEFAULT 0,
  errors_count    INTEGER NOT NULL DEFAULT 0,
  notes           TEXT
);
```

---

## 7. CLI reference

All commands are invoked as `python -m scrapper.cli <cmd>`.

| Command | What it does | Useful flags |
|---|---|---|
| `init` | Creates the 4 tables (idempotent). | — |
| `queries:gen` | Cross-joins `cities.csv` × `verticals.csv` and writes to `search_queries`. Skips duplicates. | `--country US` filter to one country · `--vertical hospitality` filter to one ICP |
| `scrape` | Runs discovery against `search_queries WHERE status='pending'`. | `--limit N` cap how many queries to run · `--headed` show the browser · `--country US` filter |
| `enrich` | Visits each business website and extracts emails + socials. | `--limit N` · `--country US` · `--retry-failed` |
| `export` | Dumps a wide CSV joining `businesses` + best-effort `contacts`. | `--out leads.csv` · `--country US` · `--vertical hospitality` · `--has-email` only rows with at least one email |
| `stats` | Prints counts: queries by status, businesses by country/vertical, contacts by kind. | — |

---

## 8. ICP & target geographies

### Verticals (`db/seeds/verticals.csv`)

| Vertical | Sample seeds |
|---|---|
| ecommerce | Shopify store, D2C brand, online boutique, e-commerce store, online retailer |
| hospitality | boutique hotel, coffee shop, spa, restaurant, yoga studio, fitness studio, beauty salon, bar |
| professional | dental clinic, law firm, physiotherapy, real estate agency, accounting firm, plastic surgeon, vet clinic, optometrist |
| b2b | digital marketing agency, SaaS company office, coworking space, consulting firm, web development agency, advertising agency, branding studio |

### Target cities (`db/seeds/cities.csv`)

| Region | Country | Cities |
|---|---|---|
| Middle East | UAE (AE) | Dubai, Abu Dhabi |
| Americas | USA (US) | New York, Los Angeles, Miami, Chicago, Austin, San Francisco, Seattle, Boston |
| Americas | Canada (CA) | Toronto, Vancouver, Montreal |
| Americas | Brazil (BR) | São Paulo, Rio de Janeiro |
| Europe | UK (GB) | London, Manchester, Edinburgh |
| Europe | Germany (DE) | Berlin, Munich, Hamburg |
| Europe | France (FR) | Paris, Lyon |
| Europe | Netherlands (NL) | Amsterdam, Rotterdam |
| Europe | Spain (ES) | Madrid, Barcelona |
| Europe | Italy (IT) | Milan, Rome |

Edit either CSV and rerun `cli queries:gen` to expand or trim the queue.

---

## 9. Bot-evasion notes

The scraper layers four mitigations:

1. **`playwright-stealth`** patches the headless browser fingerprint (navigator.webdriver, chrome runtime, plugins, languages).
2. **Random delays** between every action — see `MIN_DELAY_S` / `MAX_DELAY_S` in `.env`. Defaults to 2–7s.
3. **User-agent rotation** from a pool of recent Chrome on macOS / Windows / Linux strings.
4. **Proxy passthrough** — set `HTTP_PROXY` in `.env` and Playwright will route browser traffic through it. Residential proxies are mandatory for any sustained run.

**Captcha handling.** If `iframe[src*="recaptcha"]` is detected, the current query is marked `blocked`, the run pauses, and the operator is notified via stdout. A future enhancement could integrate a CAPTCHA-solving service (2Captcha, Anti-Captcha) — left out of v1.

---

## 10. Cost & scale

| Scenario | Method | Approx cost | Time for 10k businesses |
|---|---|---|---|
| Single dev laptop, no proxy | Playwright local | Free | ~12–24h (high block risk) |
| Local + residential proxies | Playwright + Bright Data | ~$15 / GB ≈ $30–60 | ~10–18h |
| Switch to Places API | Google Maps API New | $170 per 10k details | ~1–2h (parallelised) |
| Third-party API | SerpAPI / Outscraper | ~$10–30 per 10k | ~2–4h |

For Saflow's typical use case (1–3k leads/month per country), the proxy-Playwright path is the right starting point. If Google starts blocking, switch to the Places API — the rest of the pipeline doesn't change.

---

## 11. Roadmap

- [x] Phase 1 — Spec + scaffolding (this commit)
- [x] Phase 2 — DB layer + `cli init`
- [x] Phase 3 — Discovery scraper + `cli scrape`
- [x] Phase 4 — Enrichment + `cli enrich` / `cli export`
- [ ] Phase 5 — Cold-email outreach automation *(out of scope for v1)*
- [ ] Phase 6 — LinkedIn / Crunchbase enrichment
- [ ] Phase 7 — Lead-scoring against Saflow ICP
- [ ] Phase 8 — Web dashboard for browsing scraped leads

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `playwright._impl._errors.TimeoutError` on every query | Google captcha wall hit; selectors changed | Run with `--headed` to see what's happening; rotate proxy; bump `MIN_DELAY_S` |
| `connection refused on localhost:5432` | Postgres container not running | `docker compose up -d postgres` |
| `cli init` errors with `relation already exists` | Re-running on a populated DB | Safe to ignore (CREATE TABLE IF NOT EXISTS); or drop the DB and re-init |
| Most businesses have empty `website` | Many Google Maps listings have no website; expected. Hospitality + restaurants are the worst offenders. | — |
| Enrichment finds 0 emails on a business's home page | Email is often hidden behind a contact form; we crawl `/contact`, `/about`, `/team` automatically | Increase `ENRICH_MAX_PAGES` in `.env` if you want deeper crawls |
| `Captcha` status on many queries | Anti-bot tripped | Pause for 30+ min, lower concurrency, enable residential proxy |

---

*Last updated: 2026-05-14 · Owner: Saflow Advertising · See `scrapper/` for source.*
