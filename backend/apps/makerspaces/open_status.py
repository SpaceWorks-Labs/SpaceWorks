"""P3-4: "open now / closed, next opens at" for the public pages, from the recorded hours.

Read-only over `local_time.next_open_interval`; the bootstrap carries it ONLY when the space
records hours (`opening_hours.has_hours`), so every other space keeps a byte-identical
payload. Instants are UTC ISO strings; a client past `closes_at` / `next_opens_at` holds a
stale status and should drop it rather than guess.
"""

from django.utils import timezone

from .local_time import next_open_interval

MAX_JOINS = 14  # back-to-back daily intervals (e.g. open past midnight) read as one opening


def open_status(makerspace, now=None):
    now = now or timezone.now()
    window = next_open_interval(makerspace, now)
    if window is None:
        return {"open_now": False, "closes_at": None, "next_opens_at": None}
    start, end = window
    if start > now:
        return {"open_now": False, "closes_at": None, "next_opens_at": start.isoformat()}
    for _ in range(MAX_JOINS):
        following = next_open_interval(makerspace, end)
        if following is None or following[0] > end:
            break
        end = following[1]
    else:  # open around the clock for two weeks: no closing worth naming
        return {"open_now": True, "closes_at": None, "next_opens_at": None}
    return {"open_now": True, "closes_at": end.isoformat(), "next_opens_at": None}
