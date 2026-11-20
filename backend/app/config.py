import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _db_uri():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    path = os.path.join(BASE_DIR, "instance", "stockpilot.db").replace("\\", "/")
    return "sqlite:///" + path


class Config:
    ENV_NAME = os.getenv("APP_ENV", "development")
    DEBUG = ENV_NAME == "development"
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or secrets.token_hex(32)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7")))
    SQLALCHEMY_DATABASE_URI = _db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_ENABLED = True
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    BACKUP_FOLDER = os.path.join(BASE_DIR, "backups")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_FROM = os.getenv("MAIL_FROM", "no-reply@stockpilot.local")
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    ENV_NAME = "testing"
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    RATELIMIT_ENABLED = False
    JWT_SECRET_KEY = "test-jwt-secret-key-that-is-long-enough-123456"
    SECRET_KEY = "test-secret"
