"""Scrape the City of Geneva agenda and upsert events into Firestore."""

import argparse
import hashlib
import json
import logging
import math
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import requests

from api.config.database.db import get_db

LOGGER = logging.getLogger(__name__)
AGENDA_URL = os.getenv("AGENDA_URL", "https://www.geneve.ch/agenda")
ARTICLE_SELECTORS = ("article.event", "article[class*='event']", ".view-content article")
REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-CH,fr;q=0.9",
    "User-Agent": "Mozilla/5.0 (compatible; GenevaEventsBot/1.0)",
}
TAG_MAP = {
    "atelier": "Workshop",
    "balade - excursion": "Guided_visit",
    "cinema": "Screening",
    "conference - rencontre": "Conference_-_Meeting",
    "concert": "Concert",
    "danse": "Dance",
    "exposition": "Exhibition",
    "lecture": "Reading",
    "projection": "Screening",
    "spectacle - theatre": "Theatre",
    "sport": "Sport",
    "theatre": "Theatre",
    "visite commentee": "Guided_visit",
    "visite guidee": "Guided_visit",
}
MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}
SOURCE_NAME = "geneve_city_agenda"
LOCATION_FIELDS = (
    "venue_name", "address", "postal_code", "city", "latitude", "longitude",
    "location_status", "raw_location", "location_checked_at",
)


def _month_number(value):
    normalized = "".join(
        character for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    return MONTHS.get(value.casefold()) or MONTHS.get(normalized)


def parse_event_date(value, now=None):
    """Parse the first date from the site's French or English display text."""
    if not value:
        return None
    now = now or datetime.now()
    normalized = " ".join(value.replace("’", "'").split()).lower()
    # In "du 12 au 18 août", the month applies to both ends of the range.
    normalized = re.sub(
        r"\b(?:du\s+)?(\d{1,2})\s+(?:au|et|to|and)\s+\d{1,2}\s+([a-zàâäéèêëîïôöùûüç]+)(\s+\d{4})?",
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


def parse_event_schedule(value, now=None):
    """Return start, optional end and whether an explicit start time exists."""
    start = parse_event_date(value, now=now)
    if start is None:
        return None, None, False
    normalized = " ".join((value or "").replace("’", "'").split()).lower()
    time_match = re.search(r"(?:,|\bà\b|\bde\b)\s*(\d{1,2})h(\d{2})?\b", normalized)
    has_time = time_match is not None
    if time_match:
        hour, minute = int(time_match.group(1)), int(time_match.group(2) or 0)
        if hour > 23 or minute > 59:
            return None, None, False
        start = start.replace(hour=hour, minute=minute)

    end = None
    range_match = re.search(
        r"\b(?:du\s+)?(\d{1,2})(?:\s+([a-zàâäéèêëîïôöùûüç]+))?\s+"
        r"(?:au|to)\s+(\d{1,2})\s+([a-zàâäéèêëîïôöùûüç]+)(?:\s+(\d{4}))?",
        normalized,
    )
    if range_match:
        end_month = _month_number(range_match.group(4))
        start_month = _month_number(range_match.group(2) or range_match.group(4))
        year = int(range_match.group(5) or start.year)
        try:
            candidate_start = datetime(year, start_month, int(range_match.group(1)))
            end = datetime(year, end_month, int(range_match.group(3)))
            if end < candidate_start:
                end = end.replace(year=end.year + 1)
        except (TypeError, ValueError):
            end = None

    end_time_match = re.search(
        r"\b(?:à|au|jusqu['’]à)\s*(\d{1,2})h(\d{2})?\b", normalized[time_match.end():]
        if time_match else ""
    )
    if end_time_match:
        base = end or start
        hour, minute = int(end_time_match.group(1)), int(end_time_match.group(2) or 0)
        if hour <= 23 and minute <= 59:
            end = base.replace(hour=hour, minute=minute)
    return start, end, has_time


def _first_text(element, selectors):
    for selector in selectors:
        candidate = element.select_one(selector)
        if candidate and candidate.get_text(" ", strip=True):
            return candidate.get_text(" ", strip=True)
    return ""


def _attribute(element, selectors, attribute):
    for selector in selectors:
        candidate = element.select_one(selector)
        if candidate:
            return candidate.get(attribute, "")
    return ""


def _image_url(article, base_url):
    """Return the real URL from normal and lazy-loaded image markup."""
    candidates = article.select("img")
    for image in candidates:
        for attribute in ("data-src", "data-lazy-src", "data-original"):
            value = (image.get(attribute) or "").strip()
            if value and not value.startswith(("data:", "blob:")):
                return urljoin(base_url, value)

        srcset = (image.get("data-srcset") or image.get("srcset") or "").strip()
        if srcset:
            # The final srcset candidate is normally the highest-resolution image.
            value = srcset.split(",")[-1].strip().split()[0]
            if value and not value.startswith(("data:", "blob:")):
                return urljoin(base_url, value)

        value = (image.get("src") or "").strip()
        if value and not value.startswith(("data:", "blob:")):
            return urljoin(base_url, value)
    return ""


def normalize_tag(value):
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"\s*[–—]\s*", " - ", normalized)
    normalized = " ".join(normalized.split())
    return TAG_MAP.get(normalized, "_".join(value.split()))


def _clean_location_text(value, maximum=300):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:maximum]


def _coordinate(value, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and minimum <= number <= maximum else None


def _event_location_nodes(value):
    nodes = []
    if isinstance(value, dict):
        node_types = value.get("@type", [])
        if isinstance(node_types, str):
            node_types = [node_types]
        if "Event" in node_types and value.get("location") is not None:
            location = value["location"]
            nodes.extend(location if isinstance(location, list) else [location])
        for child in value.values():
            nodes.extend(_event_location_nodes(child))
    elif isinstance(value, list):
        for child in value:
            nodes.extend(_event_location_nodes(child))
    return nodes


def parse_location_from_html(html):
    """Extract only structured schema.org Event locations from a detail page."""
    soup = BeautifulSoup(html or "", "html.parser")
    locations = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        locations.extend(_event_location_nodes(value))

    structured = [location for location in locations if isinstance(location, dict)]
    unique = {
        json.dumps(location, ensure_ascii=False, sort_keys=True): location
        for location in structured
    }
    if not unique:
        raw_candidate = soup.select_one(".field--name-field-oa-autre-lieu")
        raw_text = _clean_location_text(
            raw_candidate.get_text(" ", strip=True) if raw_candidate else "", 1000,
        )
        return {
            "venue_name": "", "address": "", "postal_code": "", "city": "",
            "latitude": None, "longitude": None,
            "location_status": "partial" if raw_text else "missing",
            "raw_location": raw_text,
        }
    if len(unique) > 1:
        return {
            "venue_name": "", "address": "", "postal_code": "", "city": "",
            "latitude": None, "longitude": None, "location_status": "ambiguous",
            "raw_location": json.dumps(list(unique.values()), ensure_ascii=False)[:4000],
        }

    location = next(iter(unique.values()))
    address_node = location.get("address")
    if isinstance(address_node, str):
        address_node = {"streetAddress": address_node}
    if not isinstance(address_node, dict):
        address_node = {}
    geo = location.get("geo") if isinstance(location.get("geo"), dict) else {}
    venue_name = _clean_location_text(location.get("name"))
    address = _clean_location_text(address_node.get("streetAddress"))
    postal_code = _clean_location_text(address_node.get("postalCode"), 20)
    city = _clean_location_text(address_node.get("addressLocality"), 120)
    latitude = _coordinate(geo.get("latitude"), -90, 90)
    longitude = _coordinate(geo.get("longitude"), -180, 180)
    has_coordinates = latitude is not None and longitude is not None
    if has_coordinates or (venue_name and address and (postal_code or city)):
        status = "confirmed"
    elif venue_name or address or postal_code or city:
        status = "partial"
    else:
        status = "missing"
    return {
        "venue_name": venue_name,
        "address": address,
        "postal_code": postal_code,
        "city": city,
        "latitude": latitude if has_coordinates else None,
        "longitude": longitude if has_coordinates else None,
        "location_status": status,
        "raw_location": json.dumps(location, ensure_ascii=False, sort_keys=True)[:4000],
    }


def enrich_event_locations(events, existing_documents=(), session=None, now=None,
                           limit=None, delay_seconds=None):
    """Rate-limit and cache detail-page location extraction across scraper runs."""
    now = now or datetime.now(timezone.utc)
    limit = int(os.getenv("LOCATION_ENRICH_LIMIT", "20")) if limit is None else limit
    delay_seconds = (float(os.getenv("LOCATION_REQUEST_DELAY_SECONDS", "0.25"))
                     if delay_seconds is None else delay_seconds)
    refresh_days = int(os.getenv("LOCATION_REFRESH_DAYS", "30"))
    refresh_before = now - timedelta(days=refresh_days)
    existing = {
        document.id: (document.to_dict() or {})
        for document in existing_documents
    }
    session = session or requests.Session()
    session.headers.update(REQUEST_HEADERS)
    checked = 0
    for event in events:
        previous = existing.get(event["id"], {})
        last_checked = previous.get("location_checked_at")
        if isinstance(last_checked, datetime):
            if last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=timezone.utc)
            if last_checked >= refresh_before:
                continue
        if checked >= limit or not event.get("source_url"):
            continue
        if checked and delay_seconds > 0:
            time.sleep(delay_seconds)
        checked += 1
        try:
            response = session.get(event["source_url"], timeout=(10, 30))
            response.raise_for_status()
            parsed = parse_location_from_html(response.text)
        except requests.RequestException as exc:
            LOGGER.warning("Location enrichment failed for %s: %s", event["source_url"], exc)
            continue
        previous_status = previous.get("location_status")
        if (previous_status in {"confirmed", "partial", "geocoded"}
                and parsed["location_status"] in {"missing", "ambiguous"}):
            event["location_checked_at"] = now
            continue
        event.update(parsed)
        event["location_checked_at"] = now
    return checked


def parse_article(article, base_url=AGENDA_URL):
    title = _first_text(article, ("h2", "h3", "[class*='title']"))
    raw_date = _first_text(article, ("time", "[class*='date']"))
    event_date, end_date, has_start_time = parse_event_schedule(raw_date)
    if not title or event_date is None:
        LOGGER.warning("Skipping incomplete event: title=%r date=%r", title, raw_date)
        return None

    tags = [tag.get_text(" ", strip=True) for tag in article.select(".tags")]
    tag = normalize_tag(tags[-1]) if tags and tags[-1] else ""
    raw_link = _attribute(article, ("a[href*='/agenda/']", "h2 a", "h3 a"), "href")
    link = urljoin(base_url, raw_link) if raw_link else ""
    image = _image_url(article, base_url)
    description = _first_text(
        article, ("[class*='description']", "[class*='summary']", ".field--type-text", "p")
    )
    # Keep the established title/date identifier stable as richer time data is added.
    legacy_date = event_date.replace(hour=0, minute=0, second=0, microsecond=0)
    event_id = generate_event_id(title, legacy_date.isoformat())
    scraped_at = datetime.now(timezone.utc)
    article_text = article.get_text(" ", strip=True).casefold()
    return {
        "id": event_id,
        "img": image,
        "title": title,
        "date": legacy_date,
        "day": event_date.day,
        "month": event_date.month,
        "year": event_date.year,
        "description": description,
        "tag": tag,
        "source_url": link,
        "start_at": event_date,
        "end_at": end_date,
        "has_start_time": has_start_time,
        "raw_date": raw_date,
        "price_type": "free" if "100% gratuit" in article_text else "unknown",
        "source": SOURCE_NAME,
        "scraped_at": scraped_at,
        "updated_at": scraped_at,
    }


def generate_event_id(title, date):
    normalized = f"{title.strip().casefold()}|{date}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def scrape_events(url=AGENDA_URL, max_pages=None, session=None):
    """Scrape the server-rendered agenda without a browser or JavaScript runtime."""
    events = {}
    page = 0
    next_url = url
    session = session or requests.Session()
    session.headers.update(REQUEST_HEADERS)

    while max_pages is None or page < max_pages:
        page += 1
        response = session.get(next_url, timeout=(10, 30))
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        articles = None
        for selector in ARTICLE_SELECTORS:
            articles = soup.select(selector)
            if articles:
                break
        if not articles:
            raise RuntimeError(f"No event cards found on {next_url}; site markup may have changed")

        for article in articles:
            event = parse_article(article, base_url=next_url)
            if event:
                events[event["id"]] = event
        LOGGER.info("Scraped page %d (%d unique events)", page, len(events))

        next_link = soup.select_one("a[rel='next'], .pager__item--next a")
        if not next_link or not next_link.get("href"):
            break
        candidate_url = urljoin(next_url, next_link["href"])
        if candidate_url == next_url:
            break
        next_url = candidate_url

    return list(events.values())


def save_data(events, db, prune=False, existing_documents=None):
    """Upsert a complete scrape and optionally remove records no longer listed."""
    if not events:
        raise RuntimeError("Refusing to sync an empty scrape")

    existing_documents = (list(db.collection("Events").stream())
                          if existing_documents is None and prune else (existing_documents or []))
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


def main_scrape(max_pages=None, prune=False):
    if prune and max_pages is not None:
        raise ValueError("--prune cannot be combined with --max-pages")

    events = scrape_events(max_pages=max_pages)
    db = get_db()
    existing_documents = list(db.collection("Events").stream())
    enriched = enrich_event_locations(events, existing_documents=existing_documents)
    saved, deleted = save_data(
        events, db, prune=prune, existing_documents=existing_documents,
    )
    LOGGER.info("Checked location metadata for %d events", enriched)
    LOGGER.info("Synchronized %d events and removed %d stale events", saved, deleted)
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, help="limit pages (useful for smoke tests)")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="remove Firestore events absent from a successful complete scrape",
    )
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
    main_scrape(max_pages=args.max_pages, prune=args.prune)


if __name__ == "__main__":
    main()
