import json
from datetime import datetime, timezone

from scraper.scrape_articles import enrich_event_locations, parse_location_from_html


def _html(location):
    return f'''<script type="application/ld+json">{{
      "@context": "https://schema.org", "@type": "Event",
      "name": "Example", "location": {json.dumps(location)}
    }}</script>'''


def test_parses_confirmed_structured_location_and_coordinates():
    result = parse_location_from_html(_html({
        "@type": "Place", "name": "Salle communale",
        "address": {"streetAddress": "Rue du Test 4", "postalCode": "1201",
                    "addressLocality": "Genève"},
        "geo": {"latitude": 46.2044, "longitude": 6.1432},
    }))
    assert result["venue_name"] == "Salle communale"
    assert result["address"] == "Rue du Test 4"
    assert result["postal_code"] == "1201"
    assert result["city"] == "Genève"
    assert result["latitude"] == 46.2044
    assert result["location_status"] == "confirmed"


def test_incomplete_location_is_partial_without_guessing_city():
    result = parse_location_from_html(_html({
        "@type": "Place", "name": "Maison Tavel",
        "address": {"streetAddress": "Rue du Puits-Saint-Pierre 6"},
    }))
    assert result["location_status"] == "partial"
    assert result["city"] == ""
    assert result["postal_code"] == ""
    assert result["latitude"] is None


def test_rejects_malformed_coordinates_and_ambiguous_locations():
    malformed = parse_location_from_html(_html({
        "@type": "Place", "name": "Venue",
        "geo": {"latitude": "north", "longitude": 999},
    }))
    assert malformed["latitude"] is None
    assert malformed["longitude"] is None
    assert malformed["location_status"] == "partial"
    ambiguous = parse_location_from_html(_html([
        {"@type": "Place", "name": "Venue A"},
        {"@type": "Place", "name": "Venue B"},
    ]))
    assert ambiguous["location_status"] == "ambiguous"
    assert ambiguous["venue_name"] == ""


def test_missing_location_is_explicit_and_enrichment_is_cached():
    assert parse_location_from_html("<html></html>")["location_status"] == "missing"
    raw = parse_location_from_html(
        '<div class="field--name-field-oa-autre-lieu">Venue, Rue Test 1, Genève</div>'
    )
    assert raw["location_status"] == "partial"
    assert raw["raw_location"] == "Venue, Rue Test 1, Genève"
    assert raw["address"] == ""

    class Response:
        text = _html({"@type": "Place", "name": "Venue"})
        def raise_for_status(self):
            return None

    class Session:
        def __init__(self):
            self.headers = {}
            self.calls = 0
        def get(self, *_args, **_kwargs):
            self.calls += 1
            return Response()

    class Document:
        id = "cached"
        def to_dict(self):
            return {"location_checked_at": datetime(2026, 7, 10, tzinfo=timezone.utc)}

    session = Session()
    events = [
        {"id": "cached", "source_url": "https://example.test/cached"},
        {"id": "new", "source_url": "https://example.test/new"},
    ]
    checked = enrich_event_locations(
        events, [Document()], session=session,
        now=datetime(2026, 7, 14, tzinfo=timezone.utc), limit=10, delay_seconds=0,
    )
    assert checked == 1
    assert session.calls == 1
    assert events[1]["venue_name"] == "Venue"
