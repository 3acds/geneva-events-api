from datetime import date

import pytest
from werkzeug.datastructures import MultiDict

from api.routes.events.event_controller import _parse_filters


def test_combines_date_category_and_time_filters():
    result = _parse_filters(MultiDict({
        "date_from": "2026-07-14",
        "date_to": "2026-07-20",
        "category": "Concert",
        "start_time_from": "18:30",
    }))
    assert result["date_from"].isoformat() == "2026-07-14T00:00:00+02:00"
    assert result["date_to"].isoformat() == "2026-07-21T00:00:00+02:00"
    assert result["tag"] == "Concert"
    assert result["start_time_from"] == "18:30"


def test_tomorrow_filter_uses_geneva_calendar_dates():
    result = _parse_filters(MultiDict({"when": "tomorrow"}), today=date(2026, 7, 14))
    assert result["date_from"].date() == date(2026, 7, 15)
    assert result["date_to"].date() == date(2026, 7, 16)


@pytest.mark.parametrize("values,message", [
    ({"date_from": "20-07-2026"}, "YYYY-MM-DD"),
    ({"date_from": "2026-07-20", "date_to": "2026-07-14"}, "must not be after"),
    ({"when": "someday"}, "when must be"),
    ({"start_time_from": "25:00"}, "HH:MM"),
    ({"venue": "Arena"}, "Unsupported filter"),
])
def test_rejects_invalid_or_unsupported_filters(values, message):
    with pytest.raises(ValueError, match=message):
        _parse_filters(MultiDict(values))
