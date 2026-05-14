-- Saflow scraper schema. Run with:
--   psql $DATABASE_URL -f db/schema.sql
-- Or rely on `python -m scrapper.cli init` (which uses SQLAlchemy create_all).

CREATE TABLE IF NOT EXISTS search_queries (
  id              BIGSERIAL PRIMARY KEY,
  query_text      TEXT NOT NULL,
  country         TEXT NOT NULL,
  city            TEXT,
  vertical        TEXT,
  category        TEXT,
  status          TEXT NOT NULL DEFAULT 'pending',
  last_run_at     TIMESTAMPTZ,
  results_count   INTEGER NOT NULL DEFAULT 0,
  notes           TEXT,
  CONSTRAINT search_queries_unique UNIQUE (query_text, city, country)
);
CREATE INDEX IF NOT EXISTS idx_search_queries_status ON search_queries(status);

CREATE TABLE IF NOT EXISTS businesses (
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
  enrichment_status   TEXT NOT NULL DEFAULT 'pending',
  enriched_at         TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_businesses_country ON businesses(country);
CREATE INDEX IF NOT EXISTS idx_businesses_vertical ON businesses(vertical);
CREATE INDEX IF NOT EXISTS idx_businesses_enrichment_status ON businesses(enrichment_status);

CREATE TABLE IF NOT EXISTS contacts (
  id              BIGSERIAL PRIMARY KEY,
  business_id     BIGINT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  kind            TEXT NOT NULL,
  value           TEXT NOT NULL,
  source_url      TEXT,
  confidence      NUMERIC(3,2),
  is_role_based   BOOLEAN NOT NULL DEFAULT FALSE,
  found_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT contacts_unique UNIQUE (business_id, kind, value)
);
CREATE INDEX IF NOT EXISTS idx_contacts_business_id ON contacts(business_id);
CREATE INDEX IF NOT EXISTS idx_contacts_kind ON contacts(kind);

CREATE TABLE IF NOT EXISTS scrape_runs (
  id              BIGSERIAL PRIMARY KEY,
  started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at        TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'running',
  query_count     INTEGER NOT NULL DEFAULT 0,
  results_count   INTEGER NOT NULL DEFAULT 0,
  errors_count    INTEGER NOT NULL DEFAULT 0,
  notes           TEXT
);
