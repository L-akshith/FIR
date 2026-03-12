"""
ArecaMitra Backend — Configuration
Loads environment variables from .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── OpenWeather ───
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# ─── Supabase ───
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "areca-images")

# ─── ML Model ───
MODEL_PATH = os.getenv("MODEL_PATH", "areca_leaf_model.h5")
IMG_SIZE = (380, 380)

# ─── Uploads ───
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "temp_uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─── Firebase ───
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "")
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN", "arecamitra.firebaseapp.com")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "arecamitra")
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "arecamitra.firebasestorage.app")
FIREBASE_MESSAGING_SENDER_ID = os.getenv("FIREBASE_MESSAGING_SENDER_ID", "983062302029")
FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID", "")
