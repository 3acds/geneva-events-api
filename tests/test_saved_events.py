from datetime import datetime, timezone

import pytest

from api.app import app
from api.routes.saved_events import saved_event_controller


class FakeRepository:
    def __init__(self):
        self.saves = {}
        self.calls = []

    def save(self, uid, event_id):
        self.calls.append(("save", uid, event_id))
        if event_id == "deleted":
            return None
        return self.saves.setdefault((uid, event_id), {
            "event_id": event_id,
            "saved_at": datetime(2026, 7, 14, tzinfo=timezone.utc),
        })

    def remove(self, uid, event_id):
        self.calls.append(("remove", uid, event_id))
        return self.saves.pop((uid, event_id), None) is not None

    def list(self, uid):
        self.calls.append(("list", uid))
        return [{"event_id": event_id, "available": True, "event": {"id": event_id}}
                for saved_uid, event_id in self.saves if saved_uid == uid]

    def statuses(self, uid, event_ids):
        self.calls.append(("status", uid, tuple(event_ids)))
        return {event_id: (uid, event_id) in self.saves for event_id in event_ids}


@pytest.fixture
def saved_client(monkeypatch):
    repository = FakeRepository()
    monkeypatch.setattr(saved_event_controller, "saved_repository", repository)
    def verify(token):
        if token not in {"valid-a", "valid-b"}:
            raise ValueError()
        return {"uid": "user-a" if token == "valid-a" else "user-b"}
    monkeypatch.setattr("api.auth.verify_firebase_token", verify)
    app.config.update(TESTING=True)
    return app.test_client(), repository


def auth(token="valid-a"):
    return {"Authorization": f"Bearer {token}"}


def test_saved_events_require_verified_authentication(saved_client):
    client, _ = saved_client
    assert client.get("/saved-events").status_code == 401
    assert client.put("/saved-events/event-1", headers=auth("invalid")).status_code == 401


def test_authenticated_save_is_idempotent_and_uses_token_uid(saved_client):
    client, repository = saved_client
    first = client.put("/saved-events/event-1", headers=auth())
    second = client.put("/saved-events/event-1", headers=auth())
    assert first.status_code == second.status_code == 200
    assert len(repository.saves) == 1
    assert repository.calls[0] == ("save", "user-a", "event-1")


def test_unsave_and_deleted_event_handling(saved_client):
    client, _ = saved_client
    client.put("/saved-events/event-1", headers=auth())
    assert client.delete("/saved-events/event-1", headers=auth()).status_code == 204
    assert client.delete("/saved-events/event-1", headers=auth()).status_code == 204
    assert client.put("/saved-events/deleted", headers=auth()).status_code == 404


def test_users_only_see_and_modify_their_own_saves(saved_client):
    client, repository = saved_client
    client.put("/saved-events/event-1", headers=auth("valid-a"))
    assert client.get("/saved-events", headers=auth("valid-b")).get_json() == []
    client.delete("/saved-events/event-1", headers=auth("valid-b"))
    assert ("user-a", "event-1") in repository.saves


def test_status_validation_and_user_scoping(saved_client):
    client, repository = saved_client
    client.put("/saved-events/event-1", headers=auth())
    response = client.get("/saved-events/status?event_id=event-1&event_id=event-2", headers=auth())
    assert response.get_json() == {"saved": {"event-1": True, "event-2": False}}
    assert client.get("/saved-events/status", headers=auth()).status_code == 400
    assert repository.calls[-1] == ("status", "user-a", ("event-1", "event-2"))
