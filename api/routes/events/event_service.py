from .event_repository import EventRepository

##################################################
################### LOGIC ########################
##################################################
class EventService:

  def __init__(self):
    self.event_repository = EventRepository()

  def get_all_events(self):
    events = self.event_repository.fetch_all_events()
    return events

  def get_filtered_events(self, **filters):
    return self.event_repository.fetch_filtered_events(**filters)

  def get_event_by_id(self, event_id):
    return self.event_repository.fetch_event_by_id(event_id)

  def get_events_by_tag(self, event_tag):
    return self.event_repository.fetch_events_by_tag(event_tag)

  def get_events_by_date(self, day=None, month=None, year=None):
    return self.event_repository.fetch_events_by_date(day, month, year)

  def get_related_events(self, event_id, limit=4):
    event = self.event_repository.fetch_event_by_id(event_id)
    if not event:
      return None
    return self.event_repository.fetch_related_events(event, limit=limit)
