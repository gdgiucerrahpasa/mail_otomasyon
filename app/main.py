import os
import socket
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

# Railway's containers advertise IPv6 routes that don't actually have egress,
# so smtplib/imaplib pick an AAAA record for smtp.gmail.com and fail with
# "Network is unreachable". Force every DNS lookup in the process to IPv4.
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app.scheduler import scheduler, start_scheduler
from app.routes import auth, dashboard, drafts, logs
from app.routes import settings as settings_router


def _write_service_account_from_env():
    """Railway (and similar PaaS) have no place to upload credentials.json —
    paste its content into GOOGLE_CREDENTIALS_JSON instead and it's written
    to disk on every boot, since the filesystem doesn't persist across deploys."""
    raw = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if raw:
        with open("credentials.json", "w") as f:
            f.write(raw)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _write_service_account_from_env()
    init_db()
    start_scheduler()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="GDG Mail Otomasyon", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"),
    https_only=os.getenv("HTTPS_ONLY", "true").lower() == "true",
    max_age=int(os.getenv("SESSION_MAX_AGE", "43200")),
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def no_index_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(drafts.router)
app.include_router(logs.router)
app.include_router(settings_router.router)
