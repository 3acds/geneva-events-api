from flask import Flask, render_template
from flask_cors import CORS
# from flask_jwt_extended import JWTManager

# Blueprints
from routes.events.event_controller import event_blueprint
# from routes.login.login_controller import login_blueprint

app = Flask(__name__)

@app.route('/app/')
def serve_index():
    return render_template('index.html')

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
  app.run(debug=True, host='0.0.0.0', port=8080, ssl_context='adhoc')
