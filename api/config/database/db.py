import json
import os

import firebase_admin
from firebase_admin import credentials, firestore


firebase_credentials = os.environ.get("FIREBASE_CREDENTIALS_JSON")

if not firebase_credentials:
    raise RuntimeError("FIREBASE_CREDENTIALS_JSON is not configured")

credential_data = json.loads(firebase_credentials)
credential = credentials.Certificate(credential_data)

firebase_admin.initialize_app(credential)


def get_db():
    return firestore.client()
