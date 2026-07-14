import os

from flask import Flask, jsonify
from flask_cors import CORS
# from flask_jwt_extended import JWTManager

# Blueprints
from api.routes.events.event_controller import event_blueprint
from api.routes.saved_events.saved_event_controller import saved_event_blueprint
# from routes.login.login_controller import login_blueprint

app = Flask(__name__)
app.url_map.strict_slashes = False

@app.get('/health')
def health():
    return jsonify({'status': 'ok'})

# app.config['JWT_SECRET_KEY'] = 'your-secret-key'
# jwt = JWTManager(app)

default_origins = "https://gee.bsilva.ch,https://geneva-events-web.onrender.com,http://localhost:5173"
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", default_origins).split(",")
    if origin.strip()
]

CORS(
    app,
    resources={
        r"/*": {
            "origins": allowed_origins,
        }
    },
)
app.register_blueprint(event_blueprint, url_prefix='/events')
app.register_blueprint(saved_event_blueprint, url_prefix='/saved-events')
# app.register_blueprint(login_blueprint, url_prefix='/login')

if __name__ == '__main__':
  app.run(
      debug=os.getenv('FLASK_DEBUG', '').lower() == 'true',
      host='0.0.0.0',
      port=int(os.getenv('PORT', '8080')),
  )
