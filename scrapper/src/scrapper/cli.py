from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from .config import settings
from .db import Base, engine, session_scope
from .models import Business, Contact, ScrapeRun, SearchQuery  # noqa: F401  (ensure metadata registered)
from . import queries as queries_mod

app = typer.Typer(help="Saflow Google-Maps foreign-client scraper.", no_args_is_help=True)
console = Console()


def _setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command()
def init() -> None:
    """Create all tables (idempotent)."""
    _setup_logging()
    Base.metadata.create_all(engine)
    console.print("[green]✓[/green] schema created (idempotent)")


@app.command("queries:gen")
def queries_gen(
    country: str | None = typer.Option(None, "--country", help="ISO-2 country filter (e.g. AE)"),
    vertical: str | None = typer.Option(None, "--vertical", help="ecommerce|hospitality|professional|b2b"),
) -> None:
    """Generate the cities × verticals search-query queue."""
    _setup_logging()
    inserted = queries_mod.generate(country_filter=country, vertical_filter=vertical)
    console.print(f"[green]✓[/green] inserted {inserted} new queries (duplicates skipped)")


@app.command()
def scrape(
    limit: int = typer.Option(25, "--limit", help="Max number of queries to process"),
    country: str | None = typer.Option(None, "--country"),
    headed: bool = typer.Option(False, "--headed", help="Show the browser window"),
) -> None:
    """Run Google Maps discovery against pending queries."""
    _setup_logging()
    if headed:
        settings.headless = False
    from .scraper.maps import run_scrape

    summary = asyncio.run(run_scrape(limit=limit, country=country))
    console.print(
        f"[green]✓[/green] ran {summary['queries_run']} queries · "
        f"inserted {summary['results']} businesses · errors {summary['errors']}"
    )


@app.command()
def enrich(
    limit: int = typer.Option(200, "--limit"),
    country: str | None = typer.Option(None, "--country"),
    retry_failed: bool = typer.Option(False, "--retry-failed"),
) -> None:
    """Visit each business website and extract emails + social links."""
    _setup_logging()
    from .enrichment.website import run_enrichment

    summary = asyncio.run(run_enrichment(limit=limit, country=country, retry_failed=retry_failed))
    console.print(
        f"[green]✓[/green] processed {summary['businesses_processed']} businesses · "
        f"inserted {summary['contacts_inserted']} contacts"
    )


@app.command()
def export(
    out: Path = typer.Option(Path("leads.csv"), "--out"),
    country: str | None = typer.Option(None, "--country"),
    vertical: str | None = typer.Option(None, "--vertical"),
    has_email: bool = typer.Option(False, "--has-email"),
) -> None:
    """Export businesses + their best email/socials to CSV."""
    _setup_logging()
    from .exporters.csv import export_csv

    n = export_csv(out, country=country, vertical=vertical, has_email=has_email)
    console.print(f"[green]✓[/green] wrote {n} rows to {out}")


@app.command()
def stats() -> None:
    """Show counts: queries by status, businesses by country/vertical, contacts by kind."""
    _setup_logging()
    with session_scope() as s:
        q_status = list(
            s.execute(
                select(SearchQuery.status, func.count()).group_by(SearchQuery.status)
            ).all()
        )
        biz_country = list(
            s.execute(select(Business.country, func.count()).group_by(Business.country)).all()
        )
        biz_vertical = list(
            s.execute(select(Business.vertical, func.count()).group_by(Business.vertical)).all()
        )
        contact_kind = list(
            s.execute(select(Contact.kind, func.count()).group_by(Contact.kind)).all()
        )

    def _table(title: str, rows: list) -> None:
        t = Table(title=title, show_header=True)
        t.add_column("key")
        t.add_column("count", justify="right")
        for k, v in rows:
            t.add_row(str(k or "(null)"), str(v))
        console.print(t)

    _table("queries by status", q_status)
    _table("businesses by country", biz_country)
    _table("businesses by vertical", biz_vertical)
    _table("contacts by kind", contact_kind)


if __name__ == "__main__":
    app()
