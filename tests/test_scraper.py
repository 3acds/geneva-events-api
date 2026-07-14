from datetime import datetime

from bs4 import BeautifulSoup

from scraper.scrape_articles import parse_article, parse_event_schedule


def test_schedule_without_time_is_not_treated_as_midnight_event():
    start, end, has_time = parse_event_schedule(
        "Du 12 au 18 août 2026", now=datetime(2026, 1, 1)
    )
    assert start == datetime(2026, 8, 12)
    assert end == datetime(2026, 8, 18)
    assert has_time is False


def test_schedule_parses_start_and_end_times():
    start, end, has_time = parse_event_schedule(
        "Samedi 14 mars 2026, de 10h à 13h", now=datetime(2026, 1, 1)
    )
    assert start == datetime(2026, 3, 14, 10)
    assert end == datetime(2026, 3, 14, 13)
    assert has_time is True


def test_article_preserves_source_and_does_not_guess_price():
    article = BeautifulSoup(
        """<article class="event"><h2><a href="/agenda/example">Example</a></h2>
        <time>14 mars 2026, 10h</time><p>Description</p><span class="tags">Atelier</span>
        </article>""",
        "html.parser",
    ).article
    event = parse_article(article)
    assert event["source_url"] == "https://www.geneve.ch/agenda/example"
    assert event["price_type"] == "unknown"
    assert event["source"] == "geneve_city_agenda"
    assert event["raw_date"] == "14 mars 2026, 10h"


def test_article_marks_only_explicit_free_marker():
    article = BeautifulSoup(
        """<article class="event"><h2>Free event</h2><time>14 mars 2026</time>
        <p>100% gratuit</p></article>""",
        "html.parser",
    ).article
    assert parse_article(article)["price_type"] == "free"
