"""Global run state — single-process safe."""
import threading
import time

_lock = threading.Lock()
_running = False
_current_run_id: int | None = None
_stop_event = threading.Event()

# --- Login brute-force protection ---------------------------------------
_login_lock = threading.Lock()
_login_attempts: dict[str, list[float]] = {}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 15 * 60  # 15 dakika


def register_login_failure(ip: str) -> None:
    with _login_lock:
        now = time.time()
        attempts = [t for t in _login_attempts.get(ip, []) if now - t < LOGIN_ATTEMPT_WINDOW_SECONDS]
        attempts.append(now)
        _login_attempts[ip] = attempts


def is_login_blocked(ip: str) -> bool:
    with _login_lock:
        now = time.time()
        attempts = [t for t in _login_attempts.get(ip, []) if now - t < LOGIN_ATTEMPT_WINDOW_SECONDS]
        _login_attempts[ip] = attempts
        return len(attempts) >= MAX_LOGIN_ATTEMPTS


def clear_login_failures(ip: str) -> None:
    with _login_lock:
        _login_attempts.pop(ip, None)


def is_running() -> bool:
    return _running


def get_current_run_id() -> int | None:
    return _current_run_id


def acquire_run(run_id: int) -> bool:
    """Returns True if lock was acquired (run started), False if already running."""
    global _running, _current_run_id
    with _lock:
        if _running:
            return False
        _running = True
        _current_run_id = run_id
        _stop_event.clear()
        return True


def release_run():
    global _running, _current_run_id
    with _lock:
        _running = False
        _current_run_id = None


def request_stop():
    _stop_event.set()


def get_stop_event() -> threading.Event:
    return _stop_event
