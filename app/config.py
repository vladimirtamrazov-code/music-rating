import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def database_url() -> str:
    """DATABASE_URL от Render (postgres://...) приводим к драйверу psycopg 3."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        INSTANCE_DIR.mkdir(exist_ok=True)
        return f"sqlite:///{INSTANCE_DIR / 'app.db'}"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SITE_NAME = os.environ.get("SITE_NAME", "Звукоряд")

    SEED_DEMO = _env_flag("SEED_DEMO")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

    PER_PAGE = 24
    WTF_CSRF_TIME_LIMIT = None

    # Render задаёт RENDER=true — там всегда HTTPS
    ON_RENDER = _env_flag("RENDER")
    SESSION_COOKIE_SECURE = ON_RENDER
    REMEMBER_COOKIE_SECURE = ON_RENDER
    SESSION_COOKIE_SAMESITE = "Lax"
    PREFERRED_URL_SCHEME = "https" if ON_RENDER else "http"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    SEED_DEMO = False
    ADMIN_USERNAME = ADMIN_EMAIL = ADMIN_PASSWORD = None
    SESSION_COOKIE_SECURE = REMEMBER_COOKIE_SECURE = False
