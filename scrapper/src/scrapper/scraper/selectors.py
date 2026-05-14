"""Centralised selectors for Google Maps. Brittle — Google changes these frequently.

If the scraper starts returning zero results, first place to debug.
"""

RESULTS_FEED = "div[role='feed']"
RESULT_CARD_LINK = "a[href*='/maps/place/']"
RESULT_END_MARKER = "p.fontBodyMedium span:has-text(\"You've reached the end of the list.\")"

DETAIL_NAME = "h1.DUwDvf, h1[class*='DUwDvf']"
DETAIL_CATEGORY = "button[jsaction*='category']"
DETAIL_RATING = "div.fontDisplayLarge"
DETAIL_REVIEWS = "div.fontBodyMedium span[aria-label*='review']"

DETAIL_BUTTON_ADDRESS = "button[data-item-id='address']"
DETAIL_BUTTON_PHONE = "button[data-item-id^='phone:tel:']"
DETAIL_BUTTON_WEBSITE = "a[data-item-id='authority']"

CAPTCHA = "iframe[src*='recaptcha'], form[action*='sorry/index']"
