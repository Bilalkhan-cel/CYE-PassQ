"""Per-branch daily token counters, shared by the web form and the voice agent.

Rules (unchanged):
  * every branch issues at most max_tokens (800) tokens a day,
  * counters go back to 1 every day (see get_token_number in app.py),
  * no tokens after 7 PM.

The counters live in branches.json. On a read-only host (e.g. Vercel) the file
is copied to /tmp first, because /tmp is the only writable place there.
Set BRANCHES_STATE_PATH to put it somewhere else.
"""
import json
import os
import shutil
import threading
from datetime import datetime, time

CLOSING = time(19, 0)

try:
    from zoneinfo import ZoneInfo
    _PK_TZ = ZoneInfo("Asia/Karachi")
except Exception:          # no tz database available: fall back to the server clock
    _PK_TZ = None


def pk_now():
    """Current time in Pakistan. Servers such as Vercel run on UTC, and the
    7 PM rule is about the passport office's local time."""
    return datetime.now(_PK_TZ) if _PK_TZ else datetime.now()


def pk_today():
    """Today's date in Pakistan (the token "day"), not the server's UTC date."""
    return pk_now().date()

_BUNDLED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "branches.json")
_lock = threading.Lock()


def _state_path():
    custom = os.getenv("BRANCHES_STATE_PATH")
    if custom:
        return custom
    if os.access(os.path.dirname(_BUNDLED), os.W_OK):
        return _BUNDLED
    return os.path.join("/tmp", "branches.json")


STATE_PATH = _state_path()
if STATE_PATH != _BUNDLED and not os.path.exists(STATE_PATH):
    shutil.copyfile(_BUNDLED, STATE_PATH)


def _load():
    with open(STATE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(state):
    # Write to a temp file, then swap it in, so a crash never leaves half a file.
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_PATH)


data = _load()   # kept for anything that reads office.data directly


def reset():
    global data
    with _lock:
        state = _load()
        for info in state.values():
            info['current_tokens'] = 1
        _save(state)
        data = state


def branch_has_space(location):
    """Read-only: True if this branch can still issue a token today."""
    info = _load().get(location)
    return bool(info) and info['current_tokens'] <= info['max_tokens']


def check_location(location):
    """Take the next token number for this branch.

    Returns the number, None for an unknown branch, 801 when the branch is
    full for today, or 0 after closing time (all counters are reset then).
    """
    global data
    if pk_now().time() >= CLOSING:
        reset()
        return 0
    with _lock:
        state = _load()
        info = state.get(location)
        if info is None:
            return None
        if info['current_tokens'] > info['max_tokens']:
            return 801
        num = info['current_tokens']
        info['current_tokens'] += 1
        _save(state)
        data = state
        return num


def sync_counter(location, issued_number):
    """Make sure the next number handed out is after issued_number.

    Used when the database shows a number was already used (for example by
    another server instance), so two people never get the same token.
    """
    global data
    with _lock:
        state = _load()
        info = state.get(location)
        if info is not None and info['current_tokens'] <= issued_number:
            info['current_tokens'] = issued_number + 1
            _save(state)
            data = state
