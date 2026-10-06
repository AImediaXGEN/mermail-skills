#!/usr/bin/env python3
"""
mermail-opportunity-radar — reference runner (v0.1).

Turns a Mermail inbox into a zero-capital opportunity pipeline:
  1. Discover the mailbox via the Mermail REST API.
  2. List recent emails; skip ones already processed (local dedupe state).
  3. Fetch each new email; require scan_status == 'clean' before using the body.
  4. Classify: bounty / grant / rfp / hackathon / noise.
  5. Extract structured terms: reward, deadline, eligibility, submissions, sponsor, requirements.
  6. Score transparently (EV / effort / friction) and rank GO / MAYBE / NO-GO.
  7. Draft a concrete work plan for the top GO pick.

Read-only by default: never sends, applies, submits, or spends anything.

Auth: x-api-key header. Key is read from the MERMAIL_API_KEY environment
variable and never printed or written anywhere.
"""
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "https://console.mermail.app"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

MAILBOX_EMAIL = os.environ.get("MERMAIL_MAILBOX", "opportunity-radar@mermail.app")
KEY = os.environ["MERMAIL_API_KEY"]

API_CALLS = []  # (method, path, credits) — for the transparency report
_LAST_CALL = 0.0
_MIN_INTERVAL = 7.0  # Free tier is ~10 RPM; stay polite


def api(method, path, payload=None, _retried=False):
    """Minimal Mermail REST call with Free-tier rate-limit politeness."""
    global _LAST_CALL
    wait = _MIN_INTERVAL - (time.time() - _LAST_CALL)
    if wait > 0:
        time.sleep(wait)
    credits = 1 if method == "GET" else (5 if "emails" in path else 2)
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"x-api-key": KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 429 and not _retried:
            print("    (rate limit hit — backing off 65s, Free tier is ~10 RPM)")
            time.sleep(65)
            return api(method, path, payload, _retried=True)
        raise
    except (TimeoutError, ConnectionError, socket.timeout) as e:
        if not _retried:
            print(f"    (transient network error — retrying once: {e})")
            time.sleep(5)
            return api(method, path, payload, _retried=True)
        raise
    _LAST_CALL = time.time()
    API_CALLS.append((method, path, credits))
    return json.loads(body) if body else None
# __PART2__
