from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..config import settings
from ..db import session_scope
from ..models import Business, Contact
from .extractor import FoundContact, extract_emails, extract_socials

log = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[str | None, str | None]:
    try:
        r = await client.get(url, follow_redirects=True, timeout=settings.enrich_http_timeout)
        if r.status_code >= 400:
            return None, str(r.status_code)
        return r.text, None
    except Exception as e:
        return None, type(e).__name__


def _candidate_urls(base: str) -> list[str]:
    parsed = urlparse(base)
    if not parsed.scheme:
        base = "https://" + base
    return [base] + [urljoin(base, p) for p in settings.enrich_path_list][: settings.enrich_max_pages - 1]


def _insert_contacts(business_id: int, contacts: list[tuple[FoundContact, str]]) -> int:
    if not contacts:
        return 0
    rows = [
        {
            "business_id": business_id,
            "kind": c.kind,
            "value": c.value,
            "is_role_based": c.is_role_based,
            "confidence": c.confidence,
            "source_url": source,
        }
        for c, source in contacts
    ]
    with session_scope() as s:
        stmt = pg_insert(Contact).values(rows)
        stmt = stmt.on_conflict_do_nothing(constraint="contacts_unique")
        result = s.execute(stmt)
        return result.rowcount or 0


async def _enrich_business(client: httpx.AsyncClient, business_id: int, website: str) -> int:
    found: list[tuple[FoundContact, str]] = []
    for url in _candidate_urls(website):
        html, err = await _fetch(client, url)
        if err == "404":
            continue
        if not html:
            continue
        for c in extract_emails(html):
            found.append((c, url))
        for c in extract_socials(html):
            found.append((c, url))
        # If we already have an email, the rest of the pages are gravy
        if any(c[0].kind == "email" for c in found) and len(found) >= 3:
            break
    inserted = _insert_contacts(business_id, found)
    status = "done" if found else "skipped"
    with session_scope() as s:
        b = s.get(Business, business_id)
        if b:
            b.enrichment_status = status
            b.enriched_at = datetime.now(timezone.utc)
    return inserted


async def run_enrichment(
    limit: int | None = None,
    country: str | None = None,
    retry_failed: bool = False,
) -> dict:
    """Visit each pending business's website and insert any contacts found."""
    with session_scope() as s:
        q = select(Business.id, Business.website).where(Business.website.is_not(None))
        if retry_failed:
            q = q.where(Business.enrichment_status.in_(["pending", "failed"]))
        else:
            q = q.where(Business.enrichment_status == "pending")
        if country:
            q = q.where(Business.country == country.upper())
        q = q.order_by(Business.id)
        if limit:
            q = q.limit(limit)
        rows = list(s.execute(q).all())

    if not rows:
        return {"businesses_processed": 0, "contacts_inserted": 0}

    inserted_total = 0
    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        semaphore = asyncio.Semaphore(4)

        async def _bound(bid: int, website: str) -> int:
            async with semaphore:
                try:
                    return await _enrich_business(client, bid, website)
                except Exception as e:
                    log.exception("enrich failed for biz #%d: %s", bid, e)
                    with session_scope() as s:
                        b = s.get(Business, bid)
                        if b:
                            b.enrichment_status = "failed"
                    return 0

        results = await asyncio.gather(*[_bound(bid, w) for bid, w in rows])
        inserted_total = sum(results)

    return {"businesses_processed": len(rows), "contacts_inserted": inserted_total}
