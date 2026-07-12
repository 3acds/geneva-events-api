def event_to_dto(event):
    """Return the public, JSON-safe representation of an Event."""
    return event.to_dict()
