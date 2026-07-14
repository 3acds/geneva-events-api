from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify
from .event_service import EventService
from flask import request

from api.utils.decorators import error_handler
from api.execptions.NotFoundException import NotFoundException

event_blueprint = Blueprint('events', __name__)
event_service = EventService()

##################################################################
######################## ROUTES ##################################
##################################################################

# GET ALL EVENTS
@event_blueprint.route('/', methods=['GET'])
@error_handler
def get_events():
  try:
    filters = _parse_filters(request.args)
  except ValueError as exc:
    return jsonify({'error': str(exc)}), 400
  events = (event_service.get_filtered_events(**filters)
            if filters else event_service.get_all_events())
  return jsonify([event.to_dict() for event in events])


GENEVA_TZ = ZoneInfo("Europe/Zurich")


def _parse_iso_date(value, name):
  try:
    return date.fromisoformat(value)
  except ValueError as exc:
    raise ValueError(f"{name} must use YYYY-MM-DD format.") from exc


def _parse_clock(value, name):
  try:
    return time.fromisoformat(value).strftime("%H:%M")
  except ValueError as exc:
    raise ValueError(f"{name} must use HH:MM format.") from exc


def _parse_filters(args, today=None):
  supported = {'when', 'date_from', 'date_to', 'category', 'tag',
               'start_time_from', 'start_time_to'}
  unknown = set(args) - supported
  if unknown:
    raise ValueError(f"Unsupported filter(s): {', '.join(sorted(unknown))}.")
  today = today or datetime.now(GENEVA_TZ).date()
  when = args.get('when')
  start = end = None
  if when:
    if args.get('date_from') or args.get('date_to'):
      raise ValueError("when cannot be combined with date_from or date_to.")
    if when == 'today':
      start, end = today, today + timedelta(days=1)
    elif when == 'tomorrow':
      start, end = today + timedelta(days=1), today + timedelta(days=2)
    elif when == 'this_week':
      start = today
      end = today + timedelta(days=7 - today.weekday())
    elif when == 'this_weekend':
      start = today + timedelta(days=(5 - today.weekday()) % 7)
      end = start + timedelta(days=2)
    else:
      raise ValueError("when must be today, tomorrow, this_week, or this_weekend.")
  else:
    start = _parse_iso_date(args['date_from'], 'date_from') if args.get('date_from') else None
    end_date = _parse_iso_date(args['date_to'], 'date_to') if args.get('date_to') else None
    end = end_date + timedelta(days=1) if end_date else None
    if start and end_date and start > end_date:
      raise ValueError("date_from must not be after date_to.")
  start_time = (_parse_clock(args['start_time_from'], 'start_time_from')
                if args.get('start_time_from') else None)
  end_time = (_parse_clock(args['start_time_to'], 'start_time_to')
              if args.get('start_time_to') else None)
  if start_time and end_time and start_time > end_time:
    raise ValueError("start_time_from must not be after start_time_to.")
  result = {}
  if start:
    result['date_from'] = datetime.combine(start, time.min, GENEVA_TZ)
  if end:
    result['date_to'] = datetime.combine(end, time.min, GENEVA_TZ)
  tag = args.get('category') or args.get('tag')
  if args.get('category') and args.get('tag') and args['category'] != args['tag']:
    raise ValueError("category and tag cannot specify different values.")
  if tag:
    result['tag'] = tag.strip()
  if start_time:
    result['start_time_from'] = start_time
  if end_time:
    result['start_time_to'] = end_time
  return result

@event_blueprint.route('/<event_id>', methods=['GET'])
@error_handler
def get_event(event_id):
  event = event_service.get_event_by_id(event_id)
  if event:
    return jsonify(event.to_dict())
  raise NotFoundException("Event not found")
  
# GET EVENTS BY {TAG}
@event_blueprint.route('/tag/<event_tag>', methods=['GET'])
@error_handler
def get_tag(event_tag):
  events = event_service.get_events_by_tag(event_tag)
  return jsonify([event.to_dict() for event in events]), 200
  
# GET EVENTS BY {Date}
@event_blueprint.route('/date', methods=['GET'])
@error_handler
def get_date():
    day = request.args.get('day', default=None, type=int)
    month = request.args.get('month', default=None, type=int)
    year = request.args.get('year', default=None, type=int)
    
    if not any(value is not None for value in (day, month, year)):
      return jsonify({'error': 'Provide at least one of day, month, or year.'}), 400
    if day is not None and not 1 <= day <= 31:
      return jsonify({'error': 'day must be between 1 and 31.'}), 400
    if month is not None and not 1 <= month <= 12:
      return jsonify({'error': 'month must be between 1 and 12.'}), 400

    events = event_service.get_events_by_date(day=day, month=month, year=year)
    return jsonify([event.to_dict() for event in events]), 200
