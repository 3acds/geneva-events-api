from datetime import datetime

from api.config.database.db import get_db
from .event import Event


class EventRepository:
    def __init__(self, db_factory=get_db):
        self._db_factory = db_factory

    def _events(self, query):
        return [Event.from_document(document) for document in query.stream()]

    def fetch_all_events(self):
        query = self._db_factory().collection("Events").order_by("date")
        return self._events(query)

    def fetch_filtered_events(self, date_from=None, date_to=None, tag=None,
                              start_time_from=None, start_time_to=None):
        """Filter on canonical dates, retaining compatibility with legacy records.

        Date bounds run in Firestore. Optional category/time predicates run on the
        bounded result so deployments do not require a composite index merely to
        combine filters. The collection is small enough for this trade-off.
        """
        query = self._db_factory().collection("Events")
        if date_from is not None:
            query = query.where(filter=self._field_filter("date", ">=", date_from))
        if date_to is not None:
            query = query.where(filter=self._field_filter("date", "<", date_to))
        events = self._events(query.order_by("date"))
        if tag:
            normalized = tag.casefold()
            events = [event for event in events if event.tag.casefold() == normalized]
        if start_time_from or start_time_to:
            def in_time_window(event):
                value = event.start_at if isinstance(event.start_at, datetime) else event.date
                if not event.has_start_time or not isinstance(value, datetime):
                    return False
                event_time = value.strftime("%H:%M")
                return ((not start_time_from or event_time >= start_time_from) and
                        (not start_time_to or event_time <= start_time_to))
            events = [event for event in events if in_time_window(event)]
        return events

    def fetch_event_by_id(self, event_id):
        document = self._db_factory().collection("Events").document(event_id).get()
        return Event.from_document(document) if document.exists else None

    def fetch_events_by_tag(self, event_tag):
        query = self._db_factory().collection("Events").where(
            filter=self._field_filter("tag", "==", event_tag)
        )
        return self._events(query)

    def fetch_events_by_date(self, day=None, month=None, year=None):
        query = self._db_factory().collection("Events")
        for field, value in (("day", day), ("month", month), ("year", year)):
            if value is not None:
                query = query.where(filter=self._field_filter(field, "==", value))
        return self._events(query.order_by("date"))

    @staticmethod
    def _field_filter(field, operator, value):
        from google.cloud.firestore_v1.base_query import FieldFilter

        return FieldFilter(field, operator, value)
