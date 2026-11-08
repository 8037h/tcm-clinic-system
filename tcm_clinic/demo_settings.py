"""Isolated temporary public classroom demo; never points at the real database."""

from .settings import *

DEBUG = False
SECRET_KEY = os.environ["TCM_DEMO_SECRET_KEY"]
ALLOWED_HOSTS = [".trycloudflare.com", ".ngrok-free.dev", ".ngrok-free.app", "127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = ["https://*.trycloudflare.com", "https://*.ngrok-free.dev", "https://*.ngrok-free.app"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
DATABASES["default"]["NAME"] = BASE_DIR / "demo_public" / "db.sqlite3"
PERFORMANCE_ATTACHMENT_ROOT = BASE_DIR / "demo_public" / "private_uploads" / "performance"
