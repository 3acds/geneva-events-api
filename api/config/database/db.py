"""Firebase client creation.

The client is initialized lazily so importing the Flask application (or running
unit tests) does not require production credentials.
"""

import json
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_db():
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:
        raise RuntimeError("firebase-admin is not installed") from exc

    if not firebase_admin._apps:
        raw_credentials = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if raw_credentials:
            try:
                credential_data = json.loads(raw_credentials)
            except json.JSONDecodeError as exc:
                raise RuntimeError("FIREBASE_CREDENTIALS_JSON is not valid JSON") from exc
            firebase_admin.initialize_app(credentials.Certificate(credential_data))
        else:
            # Supports Application Default Credentials in Google Cloud and the
            # FIRESTORE_EMULATOR_HOST environment variable in development.
            firebase_admin.initialize_app()

    return firestore.client()
