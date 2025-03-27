import firebase_admin
from firebase_admin import credentials, firestore

# Load Firebase credentials
cred = credentials.Certificate("/var/home/ujjain/Desktop/code/termsheet_ai/termsheetai-firebase-adminsdk-fbsvc-a9cc2706a1.json")
firebase_admin.initialize_app(cred)

# Initialize Firestore DB
db = firestore.client()
