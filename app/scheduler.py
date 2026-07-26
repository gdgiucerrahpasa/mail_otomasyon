"""APScheduler setup and engine job runner."""

import logging
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app import state

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def run_engine_job():
    """Called by scheduler or manual trigger. Creates DB session, runs engine."""
    from app.database import SessionLocal
    from app.models import Run, Setting
    from app.services.engine import build_settings_dict, run_bulk_send
    from app.services.sheets import authenticate

    db = SessionLocal()
    try:
        settings = build_settings_dict(db)

        run = Run(status="running", started_at=datetime.utcnow())
        db.add(run)
        db.commit()
        db.refresh(run)

        if not state.acquire_run(run.id):
            logger.warning("Çalışan bir görev zaten var, atlandı.")
            run.status = "skipped"
            run.finished_at = datetime.utcnow()
            db.commit()
            db.close()
            return

        try:
            service = authenticate(settings["credentials_file"], settings["token_file"])
        except Exception as e:
            from app.models import LogEntry
            db.add(LogEntry(run_id=run.id, level="ERROR", message=f"Sheets bağlantısı başarısız: {e}"))
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            db.commit()
            state.release_run()
            db.close()
            return

        try:
            result = run_bulk_send(
                settings   = settings,
                service    = service,
                db         = db,
                run_id     = run.id,
                stop_event = state.get_stop_event(),
            )
            run.status    = "stopped" if state.get_stop_event().is_set() else "completed"
            run.sent      = result.sent
            run.reminded  = result.reminded
            run.skipped   = result.skipped
            run.failed    = result.failed
            run.responded = result.responded
        except Exception as e:
            from app.models import LogEntry
            db.add(LogEntry(run_id=run.id, level="ERROR", message=f"Engine hatası: {e}"))
            run.status = "failed"
        finally:
            run.finished_at = datetime.utcnow()
            db.commit()
            state.release_run()

    except Exception as e:
        logger.exception(f"run_engine_job beklenmeyen hata: {e}")
    finally:
        db.close()


def start_run_in_background():
    """Starts engine in a daemon thread. Returns False if already running."""
    if state.is_running():
        return False
    t = threading.Thread(target=run_engine_job, daemon=True)
    t.start()
    return True


def _reschedule(interval_hours: int):
    if scheduler.get_job("bulk_send"):
        scheduler.remove_job("bulk_send")
    if interval_hours > 0:
        scheduler.add_job(
            run_engine_job,
            "interval",
            hours=interval_hours,
            id="bulk_send",
            replace_existing=True,
        )
        logger.info(f"Zamanlayıcı ayarlandı: her {interval_hours} saatte bir.")


def start_scheduler():
    """Called from FastAPI lifespan. Reads schedule config from DB."""
    from app.database import SessionLocal
    from app.models import Setting

    scheduler.start()

    db = SessionLocal()
    try:
        enabled = db.query(Setting).filter_by(key="schedule_enabled").first()
        hours   = db.query(Setting).filter_by(key="schedule_interval_hours").first()
        if enabled and enabled.value.lower() == "true" and hours:
            _reschedule(int(hours.value))
    except Exception:
        pass
    finally:
        db.close()


def apply_schedule_from_db():
    """Re-reads schedule settings from DB and reschedules. Called after settings save."""
    from app.database import SessionLocal
    from app.models import Setting

    db = SessionLocal()
    try:
        enabled = db.query(Setting).filter_by(key="schedule_enabled").first()
        hours   = db.query(Setting).filter_by(key="schedule_interval_hours").first()
        if enabled and enabled.value.lower() == "true" and hours:
            _reschedule(int(hours.value))
        else:
            if scheduler.get_job("bulk_send"):
                scheduler.remove_job("bulk_send")
                logger.info("Zamanlayıcı devre dışı bırakıldı.")
    finally:
        db.close()
