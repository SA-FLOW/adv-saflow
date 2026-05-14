# Saflow Scraper — code

Code and infrastructure for the Google-Maps foreign-client scraper.

**See [`../scrapper.md`](../scrapper.md) at the repo root for the full spec, architecture, schema, CLI reference, and operator manual.**

Quickstart:

```bash
docker compose up -d postgres
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
python -m scrapper.cli init
python -m scrapper.cli queries:gen
python -m scrapper.cli scrape --limit 25
```
