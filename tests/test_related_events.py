from datetime import datetime

from api.routes.events.event import Event
from api.routes.events.event_repository import EventRepository


class Query:
    def where(self, **_kwargs):
        return self
    def order_by(self, *_args):
        return self


class Database:
    def collection(self, _name):
        return Query()


def test_related_events_rank_same_venue_category_and_date():
    source = Event(id="source", date=datetime(2026, 7, 14), tag="Concert",
                   venue_name="Victoria Hall")
    candidates = [
        Event(id="other", date=datetime(2026, 7, 15), tag="Sport", venue_name="Arena"),
        Event(id="best", date=datetime(2026, 7, 14), tag="Concert",
              venue_name="Victoria Hall"),
        Event(id="same-tag", date=datetime(2026, 7, 16), tag="Concert",
              venue_name="Elsewhere"),
        source,
    ]
    repository = EventRepository(db_factory=lambda: Database())
    repository._events = lambda _query: candidates
    related = repository.fetch_related_events(source, limit=3)
    assert [event.id for event in related] == ["best", "same-tag", "other"]
