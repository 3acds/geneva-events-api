import firebase_admin
from firebase_admin import firestore

firebase_admin.initialize_app()


def get_db():
    return firestore.client()
