from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

EMAIL_RE = re.compile(
    r"(?:[a-zA-Z0-9_!#$%&'*+/=?`{|}~^.-]+)@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}",
)

# Filters that catch obvious false-positives or junk addresses
DROP_DOMAINS = {
    "example.com",
    "domain.com",
    "yourdomain.com",
    "email.com",
    "sentry.io",
    "wixpress.com",
    "wix.com",
    "godaddy.com",
    "yourcompany.com",
}
DROP_LOCAL = {"noreply", "no-reply", "donotreply", "test", "test1", "test2", "user", "you"}

ROLE_LOCALS = {
    "info",
    "hello",
    "contact",
    "support",
    "sales",
    "admin",
    "office",
    "team",
    "help",
    "press",
    "marketing",
    "hi",
    "enquiry",
    "enquiries",
    "inquiries",
    "ask",
}

SOCIAL_HOSTS = {
    "linkedin": ("linkedin.com",),
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com", "fb.com"),
    "twitter": ("twitter.com", "x.com"),
}


@dataclass(slots=True)
class FoundContact:
    kind: str
    value: str
    is_role_based: bool = False
    confidence: float = 0.7


def extract_emails(html: str) -> list[FoundContact]:
    found: dict[str, FoundContact] = {}
    for match in EMAIL_RE.findall(html):
        email = match.lower().strip(".,;:")
        local, _, domain = email.partition("@")
        if not domain or domain in DROP_DOMAINS:
            continue
        if local in DROP_LOCAL:
            continue
        if email.endswith((".png", ".jpg", ".webp", ".gif", ".svg")):
            continue
        is_role = local in ROLE_LOCALS or local.startswith("info") or local.startswith("contact")
        confidence = 0.85 if not is_role else 0.65
        if email not in found:
            found[email] = FoundContact("email", email, is_role_based=is_role, confidence=confidence)
    return list(found.values())


def extract_socials(html: str) -> list[FoundContact]:
    found: dict[tuple[str, str], FoundContact] = {}
    for kind, hosts in SOCIAL_HOSTS.items():
        pattern = re.compile(
            r"https?://(?:www\.)?(?:" + "|".join(re.escape(h) for h in hosts) + r")/[^\s\"'<>)]+",
            re.IGNORECASE,
        )
        for m in pattern.findall(html):
            url = m.split("?", 1)[0].rstrip("/")
            # Skip share-intent URLs
            host = urlparse(url).netloc.lower()
            path = urlparse(url).path
            if not path or path == "/" or "share" in path.lower():
                continue
            key = (kind, url.lower())
            if key not in found:
                found[key] = FoundContact(kind, url, confidence=0.9)
    return list(found.values())
