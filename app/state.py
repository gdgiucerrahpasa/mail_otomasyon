"""Global run state — single-process safe."""
import threading

_lock = threading.Lock()
_running = False
_current_run_id: int | None = None
_stop_event = threading.Event()


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
