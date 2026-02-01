import os
from datetime import timedelta

# Base directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Application configuration"""

    SECRET_KEY = os.environ.get("SECRET_KEY")  # ❌ NO fallback in prod

    # Database
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL or \
        "sqlite:///" + os.path.join(BASE_DIR, "finance_app.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    # ✅ SESSION / COOKIE FIX (CRITICAL)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True

    PREFERRED_URL_SCHEME = "https"

    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    DEBUG = False
