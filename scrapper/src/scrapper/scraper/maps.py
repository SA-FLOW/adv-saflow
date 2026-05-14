from __future__ import annotations

import asyncio
import random
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

from ..config import settings
from ..db import session_scope
from ..models import Business, ScrapeRun, SearchQuery
from . import selectors as S
from .parsers import extract_latlng, extract_place_id, parse_rating, parse_reviews_count

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]


async def _sleep_jitter() -> None:
    await asyncio.sleep(random.uniform(settings.min_delay_s, settings.max_delay_s))


async def _detect_captcha(page: Page) -> bool:
    try:
        if await page.locator(S.CAPTCHA).count() > 0:
            return True
    except Exception:
        pass
    return False


async def _scroll_results(page: Page, cap: int) -> list[str]:
    """Scroll the left-hand results panel until end-of-list or cap reached.

    Returns a deduped list of /maps/place/ URLs in their displayed order.
    """
    feed = page.locator(S.RESULTS_FEED)
    seen: list[str] = []
    last_count = 0
    stagnant = 0
    while True:
        links = await feed.locator(S.RESULT_CARD_LINK).all()
        urls = []
        for link in links:
            href = await link.get_attribute("href")
            if href and href not in urls:
                urls.append(href)
        new_added = [u for u in urls if u not in seen]
        seen.extend(new_added)
        if len(seen) >= cap:
            return seen[:cap]
        # Detect end-of-list marker
        if await page.locator(S.RESULT_END_MARKER).count() > 0:
            return seen
        # If nothing changed in two consecutive scrolls, give up
        if len(seen) == last_count:
            stagnant += 1
            if stagnant >= 2:
                return seen
        else:
            stagnant = 0
        last_count = len(seen)
        await feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
        await _sleep_jitter()


async def _extract_detail(page: Page, place_url: str) -> dict | None:
    """Navigate to a place detail panel and pull fields. Returns None on failure."""
    try:
        await page.goto(place_url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_selector(S.DETAIL_NAME, timeout=15_000)
    except PlaywrightTimeout:
        log.warning("detail timeout: %s", place_url)
        return None

    if await _detect_captcha(page):
        raise RuntimeError("captcha")

    async def _safe_text(sel: str) -> str | None:
        try:
            loc = page.locator(sel).first
            if await loc.count() == 0:
                return None
            txt = await loc.inner_text(timeout=2_000)
            return txt.strip() if txt else None
        except Exception:
            return None

    async def _safe_attr(sel: str, attr: str) -> str | None:
        try:
            loc = page.locator(sel).first
            if await loc.count() == 0:
                return None
            return await loc.get_attribute(attr, timeout=2_000)
        except Exception:
            return None

    name = await _safe_text(S.DETAIL_NAME)
    if not name:
        return None

    category = await _safe_text(S.DETAIL_CATEGORY)
    rating_text = await _safe_text(S.DETAIL_RATING)
    reviews_text = await _safe_text(S.DETAIL_REVIEWS)
    address = await _safe_text(S.DETAIL_BUTTON_ADDRESS)
    phone = await _safe_text(S.DETAIL_BUTTON_PHONE)
    website = await _safe_attr(S.DETAIL_BUTTON_WEBSITE, "href")

    final_url = page.url
    place_id = extract_place_id(final_url) or extract_place_id(place_url)
    latlng = extract_latlng(final_url)

    if not place_id:
        return None

    return {
        "place_id": place_id,
        "name": name,
        "category": category,
        "address": address,
        "phone": phone,
        "website": website,
        "rating": parse_rating(rating_text),
        "reviews_count": parse_reviews_count(reviews_text),
        "lat": latlng[0] if latlng else None,
        "lng": latlng[1] if latlng else None,
        "google_url": final_url,
    }


def _upsert_business(payload: dict, query: SearchQuery) -> bool:
    """Returns True if a new row was inserted."""
    with session_scope() as s:
        stmt = pg_insert(Business).values(
            place_id=payload["place_id"],
            name=payload["name"],
            category=payload["category"],
            address=payload["address"],
            country=query.country,
            city=query.city,
            phone=payload["phone"],
            website=payload["website"],
            rating=payload["rating"],
            reviews_count=payload["reviews_count"],
            lat=payload["lat"],
            lng=payload["lng"],
            google_url=payload["google_url"],
            vertical=query.vertical,
            source_query_id=query.id,
            last_scraped_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["place_id"],
            set_={
                "phone": stmt.excluded.phone,
                "website": stmt.excluded.website,
                "rating": stmt.excluded.rating,
                "reviews_count": stmt.excluded.reviews_count,
                "last_scraped_at": stmt.excluded.last_scraped_at,
            },
        )
        result = s.execute(stmt)
        return (result.rowcount or 0) > 0


async def _launch(playwright) -> tuple[Browser, BrowserContext, Page]:
    proxy = {"server": settings.http_proxy} if settings.http_proxy else None
    browser = await playwright.chromium.launch(headless=settings.headless, proxy=proxy)
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1366, "height": 900},
        locale="en-US",
    )
    page = await context.new_page()
    if stealth_async:
        await stealth_async(page)
    return browser, context, page


async def run_scrape(limit: int | None = None, country: str | None = None) -> dict:
    """Process pending search_queries; return summary stats."""
    with session_scope() as s:
        q = select(SearchQuery).where(SearchQuery.status == "pending").order_by(SearchQuery.id)
        if country:
            q = q.where(SearchQuery.country == country.upper())
        if limit:
            q = q.limit(limit)
        queries: list[SearchQuery] = list(s.execute(q).scalars().all())
        # Detach from session — we'll re-load per query in tight scopes
        query_ids = [(qry.id, qry.query_text, qry.country, qry.city, qry.vertical) for qry in queries]

    if not query_ids:
        return {"queries_run": 0, "results": 0, "errors": 0}

    with session_scope() as s:
        run = ScrapeRun(status="running", query_count=len(query_ids))
        s.add(run)
        s.flush()
        run_id = run.id

    total_results = 0
    total_errors = 0

    async with async_playwright() as pw:
        browser, context, page = await _launch(pw)
        try:
            for qid, query_text, qcountry, qcity, qvertical in query_ids:
                log.info("query #%d: %s", qid, query_text)
                # Refetch as detached ORM object inside a fresh session for status update
                with session_scope() as s:
                    qry = s.get(SearchQuery, qid)
                    qry.status = "running"

                inserted = 0
                try:
                    url = f"https://www.google.com/maps/search/{quote_plus(query_text)}"
                    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    if await _detect_captcha(page):
                        raise RuntimeError("captcha")
                    try:
                        await page.wait_for_selector(S.RESULTS_FEED, timeout=15_000)
                    except PlaywrightTimeout:
                        log.warning("no results feed for: %s", query_text)
                        with session_scope() as s:
                            qq = s.get(SearchQuery, qid)
                            qq.status = "done"
                            qq.results_count = 0
                            qq.last_run_at = datetime.now(timezone.utc)
                        continue

                    place_urls = await _scroll_results(page, settings.max_results_per_query)
                    for place_url in place_urls:
                        await _sleep_jitter()
                        detail = await _extract_detail(page, place_url)
                        if not detail:
                            continue
                        with session_scope() as s:
                            qry_in = s.get(SearchQuery, qid)
                            if _upsert_business(detail, qry_in):
                                inserted += 1

                    with session_scope() as s:
                        qq = s.get(SearchQuery, qid)
                        qq.status = "done"
                        qq.results_count = inserted
                        qq.last_run_at = datetime.now(timezone.utc)
                    total_results += inserted
                except RuntimeError as e:
                    if str(e) == "captcha":
                        log.error("captcha wall hit on query #%d — stopping run", qid)
                        with session_scope() as s:
                            qq = s.get(SearchQuery, qid)
                            qq.status = "blocked"
                            qq.notes = "captcha"
                        total_errors += 1
                        break
                    raise
                except Exception as e:
                    log.exception("query #%d failed: %s", qid, e)
                    with session_scope() as s:
                        qq = s.get(SearchQuery, qid)
                        qq.status = "failed"
                        qq.notes = str(e)[:500]
                    total_errors += 1
        finally:
            await context.close()
            await browser.close()

    with session_scope() as s:
        run = s.get(ScrapeRun, run_id)
        run.status = "success" if total_errors == 0 else "completed_with_errors"
        run.results_count = total_results
        run.errors_count = total_errors
        run.ended_at = datetime.now(timezone.utc)

    return {"queries_run": len(query_ids), "results": total_results, "errors": total_errors}
