import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app.scheduler import scheduler, start_scheduler
from app.routes import auth, dashboard, drafts, logs
from app.routes import settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(drafts.router)
app.include_router(logs.router)
app.include_router(settings_router.router)
