"""Firebase client creation.

The client is initialized lazily so importing the Flask application (or running
unit tests) does not require production credentials.
"""

import json
import os
from functools import lru_cache


def _get_firebase_app():
    try:
        import firebase_admin
        from firebase_admin import credentials
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

    return firebase_admin.get_app()


@lru_cache(maxsize=1)
def get_db():
    try:
        from firebase_admin import firestore
    except ImportError as exc:
        raise RuntimeError("firebase-admin is not installed") from exc

    _get_firebase_app()

    return firestore.client()


@lru_cache(maxsize=1)
def get_bucket():
    try:
        from firebase_admin import storage
    except ImportError as exc:
        raise RuntimeError("firebase-admin is not installed") from exc

    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
    if not bucket_name:
        raise RuntimeError("FIREBASE_STORAGE_BUCKET is not configured")

    _get_firebase_app()
    return storage.bucket(bucket_name)
