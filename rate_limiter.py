"""
Rate limiting for outbound Claude API calls, so a burst of Telegram taps (or a
runaway loop) can't blow through the API budget.

Two independent caps, both checked by allow_call() before every request:
  1. A sliding per-minute window -- bursts are throttled (the caller briefly
     blocks until a slot frees up), not dropped, since "5 articles from one
     theme tap" is normal usage, not abuse.
  2. A hard daily call budget persisted to disk -- once exhausted, calls are
     refused outright rather than delayed, so cumulative spend can't run away
     across bot restarts.
"""

import os
import json
import time
import logging
from collections import deque
from datetime import datetime, timezone
from threading import Lock

logger = logging.getLogger(__name__)

_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rate_limit_state.json")

MAX_CALLS_PER_MINUTE = int(os.getenv("CLAUDE_MAX_CALLS_PER_MINUTE", "10"))
MAX_CALLS_PER_DAY = int(os.getenv("CLAUDE_MAX_CALLS_PER_DAY", "200"))

_lock = Lock()
_call_times = deque()  # monotonic timestamps of calls within the last 60s


def _load_daily_state() -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    if os.path.exists(_STATE_PATH):
        try:
            with open(_STATE_PATH, "r") as f:
                state = json.load(f)
            if state.get("date") == today:
                return state
        except (json.JSONDecodeError, OSError):
            pass
    return {"date": today, "count": 0}


def _save_daily_state(state: dict) -> None:
    try:
        with open(_STATE_PATH, "w") as f:
            json.dump(state, f)
    except OSError as e:
        logger.warning(f"Could not persist rate-limit state: {e}")


def allow_call() -> bool:
    """
    Call immediately before every Claude API request.

    Returns True once a slot is reserved (may sleep first to satisfy the
    per-minute window). Returns False -- without sleeping -- if today's call
    budget is already exhausted, meaning the caller should skip the request
    entirely rather than spend more.
    """
    with _lock:
        state = _load_daily_state()
        if state["count"] >= MAX_CALLS_PER_DAY:
            logger.warning(f"Daily Claude call budget ({MAX_CALLS_PER_DAY}) exhausted -- skipping call.")
            return False

        now = time.monotonic()
        while _call_times and now - _call_times[0] >= 60:
            _call_times.popleft()

        sleep_for = 0.0
        if len(_call_times) >= MAX_CALLS_PER_MINUTE:
            sleep_for = 60 - (now - _call_times[0]) + 0.05

    if sleep_for > 0:
        logger.info(f"Per-minute Claude call limit ({MAX_CALLS_PER_MINUTE}) reached, waiting {sleep_for:.1f}s.")
        time.sleep(sleep_for)

    with _lock:
        now = time.monotonic()
        while _call_times and now - _call_times[0] >= 60:
            _call_times.popleft()
        _call_times.append(now)

        state = _load_daily_state()
        state["count"] += 1
        _save_daily_state(state)

    return True
