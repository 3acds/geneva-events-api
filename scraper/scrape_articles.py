"""Scrape the City of Geneva agenda and upsert events into Firestore."""

import argparse
import hashlib
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dateutil import parser as date_parser
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from api.config.database.db import get_db

LOGGER = logging.getLogger(__name__)
AGENDA_URL = os.getenv("AGENDA_URL", "https://www.geneve.ch/agenda")
ARTICLE_SELECTORS = ("article.event", "article[class*='event']", ".view-content article")
MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}


def parse_event_date(value, now=None):
    """Parse the first date from the site's French or English display text."""
    if not value:
        return None
    now = now or datetime.now()
    normalized = " ".join(value.replace("’", "'").split()).lower()
    # In "du 12 au 18 août", the month applies to both ends of the range.
    normalized = re.sub(
        r"\b(?:du\s+)?(\d{1,2})\s+(?:au|to)\s+\d{1,2}\s+([a-zàâäéèêëîïôöùûüç]+)(\s+\d{4})?",
        r"\1 \2\3",
        normalized,
    )
    match = re.search(
        r"(?:du|from)?\s*(\d{1,2})\s+([a-zàâäéèêëîïôöùûüç]+)(?:\s+(\d{4}))?",
        normalized,
    )
    if match and match.group(2) in MONTHS:
        day = int(match.group(1))
        month = MONTHS[match.group(2)]
        year = int(match.group(3) or now.year)
        # Agenda pages can contain next year's events near year-end.
        if not match.group(3) and month < now.month - 6:
            year += 1
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    try:
        parsed = date_parser.parse(value, fuzzy=True, dayfirst=True, default=now)
        return parsed.replace(hour=0, minute=0, second=0, microsecond=0)
    except (ValueError, OverflowError):
        return None


def _first_text(element, selectors):
    for selector in selectors:
        candidates = element.find_elements(By.CSS_SELECTOR, selector)
        if candidates and candidates[0].text.strip():
            return candidates[0].text.strip()
    return ""


def _attribute(element, selectors, attribute):
    for selector in selectors:
        candidates = element.find_elements(By.CSS_SELECTOR, selector)
        if candidates:
            return candidates[0].get_attribute(attribute) or ""
    return ""


def _image_url(article, base_url):
    """Return the real URL from normal and lazy-loaded image markup."""
    candidates = article.find_elements(By.CSS_SELECTOR, "img")
    for image in candidates:
        for attribute in ("data-src", "data-lazy-src", "data-original"):
            value = (image.get_attribute(attribute) or "").strip()
            if value and not value.startswith(("data:", "blob:")):
                return urljoin(base_url, value)

        srcset = (image.get_attribute("data-srcset") or image.get_attribute("srcset") or "").strip()
        if srcset:
            # The final srcset candidate is normally the highest-resolution image.
            value = srcset.split(",")[-1].strip().split()[0]
            if value and not value.startswith(("data:", "blob:")):
                return urljoin(base_url, value)

        value = (image.get_attribute("src") or "").strip()
        if value and not value.startswith(("data:", "blob:")):
            return urljoin(base_url, value)
    return ""


def parse_article(article, base_url=AGENDA_URL):
    title = _first_text(article, ("h2", "h3", "[class*='title']"))
    raw_date = _first_text(article, ("time", "[class*='date']"))
    event_date = parse_event_date(raw_date)
    if not title or event_date is None:
        LOGGER.warning("Skipping incomplete event: title=%r date=%r", title, raw_date)
        return None

    tags = article.find_elements(By.CSS_SELECTOR, ".tags a, [class*='tag'] a, [class*='category']")
    tag = "_".join(tags[-1].text.strip().split()) if tags and tags[-1].text.strip() else ""
    raw_link = _attribute(article, ("h2 a", "h3 a", "a[href*='/agenda/']"), "href")
    link = urljoin(base_url, raw_link) if raw_link else ""
    image = _image_url(article, base_url)
    description = _first_text(
        article, ("[class*='description']", "[class*='summary']", ".field--type-text", "p")
    )
    iso_date = event_date.isoformat()
    event_id = generate_event_id(title, iso_date)
    return {
        "id": event_id,
        "img": image,
        "title": title,
        "date": event_date,
        "day": event_date.day,
        "month": event_date.month,
        "year": event_date.year,
        "description": description,
        "tag": tag,
        "source_url": link,
    }


def generate_event_id(title, date):
    normalized = f"{title.strip().casefold()}|{date}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def create_driver(headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    # Selenium Manager resolves a compatible driver; no per-run driver download.
    return webdriver.Chrome(options=options)


def scrape_events(driver, url=AGENDA_URL, max_pages=None):
    events = {}
    page = 0
    driver.get(url)
    wait = WebDriverWait(driver, 20)
    while max_pages is None or page < max_pages:
        page += 1
        articles = []
        for selector in ARTICLE_SELECTORS:
            try:
                articles = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                if articles:
                    break
            except TimeoutException:
                continue
        if not articles:
            raise RuntimeError(f"No event cards found on {driver.current_url}; site markup may have changed")
        for article in articles:
            # Scrolling activates the agenda's native lazy-loading attributes.
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", article)
            event = parse_article(article, base_url=driver.current_url)
            if event:
                events[event["id"]] = event
        LOGGER.info("Scraped page %d (%d unique events)", page, len(events))
        try:
            next_link = driver.find_element(By.CSS_SELECTOR, "a[rel='next'], .pager__item--next a")
            next_url = next_link.get_attribute("href")
        except NoSuchElementException:
            break
        if not next_url or next_url == driver.current_url:
            break
        driver.get(next_url)
    return list(events.values())


def save_data(events, db, prune=False):
    """Upsert a complete scrape and optionally remove records no longer listed."""
    if not events:
        raise RuntimeError("Refusing to sync an empty scrape")

    existing_documents = list(db.collection("Events").stream()) if prune else []
    minimum_ratio = float(os.getenv("PRUNE_MIN_RATIO", "0.5"))
    if existing_documents and len(events) < len(existing_documents) * minimum_ratio:
        raise RuntimeError(
            "Refusing to prune: scrape returned "
            f"{len(events)} events for {len(existing_documents)} existing records"
        )

    saved = 0
    for offset in range(0, len(events), 500):
        batch = db.batch()
        chunk = events[offset:offset + 500]
        for event in chunk:
            reference = db.collection("Events").document(event["id"])
            batch.set(reference, event, merge=True)
        batch.commit()
        saved += len(chunk)

    deleted = 0
    if prune:
        scraped_ids = {event["id"] for event in events}
        stale_references = [
            document.reference
            for document in existing_documents
            if document.id not in scraped_ids
        ]
        for offset in range(0, len(stale_references), 500):
            batch = db.batch()
            chunk = stale_references[offset:offset + 500]
            for reference in chunk:
                batch.delete(reference)
            batch.commit()
            deleted += len(chunk)

    return saved, deleted


def main_scrape(max_pages=None, headless=True, prune=False):
    if prune and max_pages is not None:
        raise ValueError("--prune cannot be combined with --max-pages")

    driver = create_driver(headless=headless)
    try:
        events = scrape_events(driver, max_pages=max_pages)
    finally:
        driver.quit()
    saved, deleted = save_data(events, get_db(), prune=prune)
    LOGGER.info("Synchronized %d events and removed %d stale events", saved, deleted)
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, help="limit pages (useful for smoke tests)")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="remove Firestore events absent from a successful complete scrape",
    )
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
    main_scrape(max_pages=args.max_pages, headless=not args.show_browser, prune=args.prune)


if __name__ == "__main__":
    main()
