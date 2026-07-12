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
