from datetime import datetime, timezone

from api.routes.events.event import Event


def test_event_serializes_normalized_timestamps():
    event = Event(title="Example", start_at=datetime(2026, 7, 14, 18, tzinfo=timezone.utc))
    assert event.to_dict()["start_at"] == "2026-07-14T18:00:00+00:00"
    assert event.to_dict()["end_at"] is None
