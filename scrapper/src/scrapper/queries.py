from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert

from .db import session_scope
from .models import SearchQuery

SEEDS_DIR = Path(__file__).resolve().parents[2] / "db" / "seeds"
CITIES_CSV = SEEDS_DIR / "cities.csv"
VERTICALS_CSV = SEEDS_DIR / "verticals.csv"


def _load_cities() -> list[tuple[str, str]]:
    with CITIES_CSV.open() as f:
        reader = csv.DictReader(f)
        return [(row["country"].strip(), row["city"].strip()) for row in reader]


def _load_verticals() -> list[tuple[str, str]]:
    with VERTICALS_CSV.open() as f:
        reader = csv.DictReader(f)
        return [(row["vertical"].strip(), row["seed"].strip()) for row in reader]


def generate(country_filter: str | None = None, vertical_filter: str | None = None) -> int:
    cities = _load_cities()
    verticals = _load_verticals()

    if country_filter:
        cities = [c for c in cities if c[0] == country_filter.upper()]
    if vertical_filter:
        verticals = [v for v in verticals if v[0] == vertical_filter.lower()]

    rows = []
    for country, city in cities:
        for vertical, seed in verticals:
            rows.append(
                {
                    "query_text": f"{seed} in {city}",
                    "country": country,
                    "city": city,
                    "vertical": vertical,
                    "category": seed,
                    "status": "pending",
                }
            )

    if not rows:
        return 0

    with session_scope() as s:
        stmt = pg_insert(SearchQuery).values(rows)
        stmt = stmt.on_conflict_do_nothing(constraint="search_queries_unique")
        result = s.execute(stmt)
        return result.rowcount or 0
