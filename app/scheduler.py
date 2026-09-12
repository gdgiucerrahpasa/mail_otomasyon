"""APScheduler setup and engine job runner."""

import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import state

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

# Türkiye saati DST kullanmıyor, sabit UTC+3 — sunucunun kendi saat dilimi
# ne olursa olsun (Oracle VM'ler genelde UTC), kullanıcının girdiği saat
# hep TR saatine göre tetiklensin diye trigger'a açıkça bu tz veriliyor.
TR_TZ = ZoneInfo("Europe/Istanbul")


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


def _reschedule(mode: str, interval_hours: int, time_str: str):
    if scheduler.get_job("bulk_send"):
        scheduler.remove_job("bulk_send")

    if mode == "daily":
        try:
            hour, minute = (int(p) for p in time_str.strip().split(":", 1))
        except (ValueError, AttributeError):
            hour, minute = 9, 0
        scheduler.add_job(
            run_engine_job,
            CronTrigger(hour=hour, minute=minute, timezone=TR_TZ),
            id="bulk_send",
            replace_existing=True,
        )
        logger.info(f"Zamanlayıcı ayarlandı: her gün {hour:02d}:{minute:02d} (TR saati).")
    elif interval_hours > 0:
        scheduler.add_job(
            run_engine_job,
            "interval",
            hours=interval_hours,
            id="bulk_send",
            replace_existing=True,
        )
        logger.info(f"Zamanlayıcı ayarlandı: her {interval_hours} saatte bir.")


def _read_schedule_config(db) -> dict:
    from app.models import Setting
    s = {r.key: r.value for r in db.query(Setting).all()}
    return {
        "enabled":  s.get("schedule_enabled", "false").lower() == "true",
        "mode":     s.get("schedule_mode", "interval"),
        "hours":    int(s.get("schedule_interval_hours", "6") or 6),
        "time":     s.get("schedule_time", "09:00"),
    }


def start_scheduler():
    """Called from FastAPI lifespan. Reads schedule config from DB."""
    from app.database import SessionLocal

    scheduler.start()

    db = SessionLocal()
    try:
        cfg = _read_schedule_config(db)
        if cfg["enabled"]:
            _reschedule(cfg["mode"], cfg["hours"], cfg["time"])
    except Exception:
        pass
    finally:
        db.close()


def apply_schedule_from_db():
    """Re-reads schedule settings from DB and reschedules. Called after settings save."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        cfg = _read_schedule_config(db)
        if cfg["enabled"]:
            _reschedule(cfg["mode"], cfg["hours"], cfg["time"])
        else:
            if scheduler.get_job("bulk_send"):
                scheduler.remove_job("bulk_send")
                logger.info("Zamanlayıcı devre dışı bırakıldı.")
    finally:
        db.close()
