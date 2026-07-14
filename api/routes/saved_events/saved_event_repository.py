from datetime import datetime, timezone

from api.config.database.db import get_db
from api.routes.events.event import Event


class SavedEventRepository:
    def __init__(self, db_factory=get_db):
        self._db_factory = db_factory

    def _saved(self, uid):
        return self._db_factory().collection("users").document(uid).collection("saved_events")

    def save(self, uid, event_id):
        event_ref = self._db_factory().collection("Events").document(event_id)
        if not event_ref.get().exists:
            return None
        saved_ref = self._saved(uid).document(event_id)
        snapshot = saved_ref.get()
        if snapshot.exists:
            return snapshot.to_dict()
        record = {"event_id": event_id, "saved_at": datetime.now(timezone.utc)}
        saved_ref.set(record)
        return record

    def remove(self, uid, event_id):
        saved_ref = self._saved(uid).document(event_id)
        existed = saved_ref.get().exists
        if existed:
            saved_ref.delete()
        return existed

    def list(self, uid):
        records = []
        for saved in self._saved(uid).stream():
            data = saved.to_dict() or {}
            event_id = data.get("event_id") or saved.id
            event_snapshot = self._db_factory().collection("Events").document(event_id).get()
            event = Event.from_document(event_snapshot).to_dict() if event_snapshot.exists else None
            saved_at = data.get("saved_at")
            records.append({
                "event_id": event_id,
                "saved_at": saved_at.isoformat() if hasattr(saved_at, "isoformat") else saved_at,
                "available": event is not None,
                "event": event,
            })
        return records

    def statuses(self, uid, event_ids):
        return {
            event_id: self._saved(uid).document(event_id).get().exists
            for event_id in event_ids
        }
