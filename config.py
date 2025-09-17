import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Secret key for sessions & CSRF
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    # ✅ Database URI (SQLite dalam folder instance/)
    # Kelebihan: file database tak termasuk dalam Git sebab instance/ boleh di-.gitignore
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")  # boleh override dengan env var
        or "sqlite:///" + os.path.join(BASE_DIR, "instance", "database.db")
    )

    # Disable modification tracking untuk performance
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Folder untuk upload files (e.g. CSV import)
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or os.path.join(BASE_DIR, "uploads")

    # Limit saiz upload (default 5 MB)
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH") or 5 * 1024 * 1024)