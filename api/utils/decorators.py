from functools import wraps
from flask import current_app, jsonify

from api.execptions.NotFoundException import NotFoundException

# Status code handling (ERRORS)
def error_handler(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    try:
      return f(*args, **kwargs)
    except NotFoundException as e:
      return jsonify({'error': str(e)}), 404
    except RuntimeError as e:
      current_app.logger.exception("Service configuration error")
      return jsonify({'error': str(e)}), 503
    except Exception:
      current_app.logger.exception("Unhandled request error")
      return jsonify({'error': 'Internal server error'}), 500
  return decorated_function
