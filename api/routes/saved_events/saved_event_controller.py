from flask import Blueprint, g, jsonify, request

from api.auth import require_auth
from api.utils.decorators import error_handler
from .saved_event_repository import SavedEventRepository

saved_event_blueprint = Blueprint("saved_events", __name__)
saved_repository = SavedEventRepository()


@saved_event_blueprint.get("")
@require_auth
@error_handler
def list_saved_events():
    return jsonify(saved_repository.list(g.current_user["uid"]))


@saved_event_blueprint.put("/<event_id>")
@require_auth
@error_handler
def save_event(event_id):
    record = saved_repository.save(g.current_user["uid"], event_id)
    if record is None:
        return jsonify({"error": "Event not found."}), 404
    saved_at = record.get("saved_at")
    return jsonify({
        "event_id": event_id,
        "saved": True,
        "saved_at": saved_at.isoformat() if hasattr(saved_at, "isoformat") else saved_at,
    })


@saved_event_blueprint.delete("/<event_id>")
@require_auth
@error_handler
def remove_saved_event(event_id):
    saved_repository.remove(g.current_user["uid"], event_id)
    return "", 204


@saved_event_blueprint.get("/status")
@require_auth
@error_handler
def saved_statuses():
    event_ids = [value.strip() for value in request.args.getlist("event_id") if value.strip()]
    if not event_ids:
        return jsonify({"error": "At least one event_id is required."}), 400
    if len(event_ids) > 100 or any(len(value) > 200 for value in event_ids):
        return jsonify({"error": "Invalid event_id selection."}), 400
    return jsonify({"saved": saved_repository.statuses(g.current_user["uid"], event_ids)})
