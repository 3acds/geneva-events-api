import os

from flask import Flask, jsonify
from flask_cors import CORS
# from flask_jwt_extended import JWTManager

# Blueprints
from api.routes.events.event_controller import event_blueprint
# from routes.login.login_controller import login_blueprint

app = Flask(__name__)

@app.get('/health')
def health():
    return jsonify({'status': 'ok'})

# app.config['JWT_SECRET_KEY'] = 'your-secret-key'
# jwt = JWTManager(app)

cors = CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "https://gee.bsilva.ch",
                "http://localhost:5173",
            ]
        }
    },
)
app.register_blueprint(event_blueprint, url_prefix='/events')
# app.register_blueprint(login_blueprint, url_prefix='/login')

if __name__ == '__main__':
  app.run(
      debug=os.getenv('FLASK_DEBUG', '').lower() == 'true',
      host='0.0.0.0',
      port=int(os.getenv('PORT', '8080')),
  )
