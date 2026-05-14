from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select

from ..db import session_scope
from ..models import Business, Contact


HEADER = [
    "name",
    "country",
    "city",
    "vertical",
    "category",
    "address",
    "phone",
    "website",
    "email",
    "email_role_based",
    "linkedin",
    "instagram",
    "facebook",
    "twitter",
    "rating",
    "reviews_count",
    "google_url",
    "place_id",
]


def _pick_best_email(contacts: list[Contact]) -> tuple[str, bool]:
    emails = [c for c in contacts if c.kind == "email"]
    if not emails:
        return "", False
    # Prefer non-role-based over role-based
    non_role = [c for c in emails if not c.is_role_based]
    chosen = non_role[0] if non_role else emails[0]
    return chosen.value, chosen.is_role_based


def _socials(contacts: list[Contact]) -> dict[str, str]:
    out = {"linkedin": "", "instagram": "", "facebook": "", "twitter": ""}
    for c in contacts:
        if c.kind in out and not out[c.kind]:
            out[c.kind] = c.value
    return out


def export_csv(
    out_path: Path,
    country: str | None = None,
    vertical: str | None = None,
    has_email: bool = False,
) -> int:
    with session_scope() as s:
        q = select(Business)
        if country:
            q = q.where(Business.country == country.upper())
        if vertical:
            q = q.where(Business.vertical == vertical.lower())
        businesses = list(s.execute(q).scalars().all())

        rows_written = 0
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADER)
            writer.writeheader()
            for b in businesses:
                contacts = list(b.contacts)
                email, role = _pick_best_email(contacts)
                if has_email and not email:
                    continue
                socials = _socials(contacts)
                writer.writerow(
                    {
                        "name": b.name,
                        "country": b.country,
                        "city": b.city or "",
                        "vertical": b.vertical or "",
                        "category": b.category or "",
                        "address": b.address or "",
                        "phone": b.phone or "",
                        "website": b.website or "",
                        "email": email,
                        "email_role_based": "yes" if role else "",
                        "linkedin": socials["linkedin"],
                        "instagram": socials["instagram"],
                        "facebook": socials["facebook"],
                        "twitter": socials["twitter"],
                        "rating": str(b.rating) if b.rating is not None else "",
                        "reviews_count": b.reviews_count if b.reviews_count is not None else "",
                        "google_url": b.google_url or "",
                        "place_id": b.place_id,
                    }
                )
                rows_written += 1
        return rows_written
