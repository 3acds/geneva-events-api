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
  events = event_service.get_all_events()
  return jsonify([event.to_dict() for event in events])

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
