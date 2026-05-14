from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import unquote

PLACE_ID_PATTERNS = [
    re.compile(r"!1s([^!]+)!"),
    re.compile(r"data=.*?0x[0-9a-fA-F]+:0x[0-9a-fA-F]+"),
]

LATLNG_PATTERN = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")
REVIEWS_PATTERN = re.compile(r"([\d,]+)")


def extract_place_id(url: str) -> str | None:
    """Pull a stable Google Maps place identifier out of a maps URL.

    Google Maps doesn't expose the canonical Places API place_id directly in the
    UI URL — we use the `!1s` token which is stable per business.
    """
    m = PLACE_ID_PATTERNS[0].search(url)
    if m:
        return unquote(m.group(1))
    m = PLACE_ID_PATTERNS[1].search(url)
    if m:
        return m.group(0).split("data=", 1)[-1]
    return None


def extract_latlng(url: str) -> tuple[Decimal, Decimal] | None:
    m = LATLNG_PATTERN.search(url)
    if not m:
        return None
    return Decimal(m.group(1)), Decimal(m.group(2))


def parse_reviews_count(text: str | None) -> int | None:
    if not text:
        return None
    m = REVIEWS_PATTERN.search(text)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def parse_rating(text: str | None) -> Decimal | None:
    if not text:
        return None
    try:
        return Decimal(text.strip().split()[0].replace(",", "."))
    except Exception:
        return None
