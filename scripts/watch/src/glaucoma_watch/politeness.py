"""Per-host politeness: robots.txt compliance and rate limiting.

Two enterprise-grade guarantees this module enforces:

1. **robots.txt** is honored. The watcher's User-Agent string is checked
   against the published rules for each host. Disallowed URLs are skipped with
   a logged ``robots_disallow`` event so the audit trail records every URL we
   refused to fetch and why.
2. **Per-host rate limit** prevents bursting against a single domain. A simple
   token bucket per host (default: 1 request / 2 seconds) is enforced with
   a process-local lock so concurrent runs in the same Python process do not
   bypass it.

Tunable via environment variables:

* ``RETINA_WATCH_DISABLE_ROBOTS=1`` skips the robots.txt check (testing only).
* ``RETINA_WATCH_MIN_INTERVAL_SECONDS`` overrides the default 2.0s interval.
"""

from __future__ import annotations

import os
import threading
import time
import urllib.robotparser as robotparser
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

from .logging_setup import get_logger


_USER_AGENT = "glaucoma-watch/0.1"


@dataclass
class _HostState:
    last_request_at: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)
    robots: robotparser.RobotFileParser | None = None
    robots_loaded: bool = False


_state: dict[str, _HostState] = {}
_state_lock = threading.Lock()


def _host_state(host: str) -> _HostState:
    with _state_lock:
        st = _state.get(host)
        if st is None:
            st = _HostState()
            _state[host] = st
        return st


def _min_interval() -> float:
    raw = os.environ.get("RETINA_WATCH_MIN_INTERVAL_SECONDS")
    try:
        return float(raw) if raw is not None else 2.0
    except ValueError:
        return 2.0


def _robots_disabled() -> bool:
    return os.environ.get("RETINA_WATCH_DISABLE_ROBOTS") == "1"


def _load_robots(host_state: _HostState, scheme: str, host: str) -> None:
    if host_state.robots_loaded:
        return
    rp = robotparser.RobotFileParser()
    robots_url = f"{scheme}://{host}/robots.txt"
    rp.set_url(robots_url)
    try:
        resp = requests.get(robots_url, timeout=10, headers={"User-Agent": _USER_AGENT})
        if resp.status_code >= 400:
            rp.parse([])
        else:
            rp.parse(resp.text.splitlines())
    except Exception as exc:
        get_logger().warning("robots_fetch_failed", host=host, error=str(exc))
        rp.parse([])
    host_state.robots = rp
    host_state.robots_loaded = True


def robots_allows(url: str, user_agent: str = _USER_AGENT) -> bool:
    if _robots_disabled():
        return True
    parsed = urlparse(url)
    if not parsed.netloc:
        return True
    st = _host_state(parsed.netloc)
    _load_robots(st, parsed.scheme or "https", parsed.netloc)
    if st.robots is None:
        return True
    return bool(st.robots.can_fetch(user_agent, url))


def wait_for_host(url: str, interval: float | None = None) -> float:
    """Block until the per-host rate limit permits another request.

    Returns the number of seconds spent waiting (0.0 if no wait was required).
    """
    parsed = urlparse(url)
    if not parsed.netloc:
        return 0.0
    st = _host_state(parsed.netloc)
    min_int = interval if interval is not None else _min_interval()
    with st.lock:
        now = time.monotonic()
        elapsed = now - st.last_request_at if st.last_request_at else min_int
        if elapsed < min_int:
            wait = min_int - elapsed
            time.sleep(wait)
            st.last_request_at = time.monotonic()
            return wait
        st.last_request_at = now
        return 0.0
