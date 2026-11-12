"""Bounded GraphQL calendar fetch. Never called by a public read."""

import json
import logging
import re
import urllib.request
from datetime import date

from django.conf import settings

logger = logging.getLogger(__name__)
GRAPHQL_URL = "https://api.github.com/graphql"
REQUEST_TIMEOUT = 8
MAX_RESPONSE_BYTES = 128 * 1024
USERNAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""


def configured():
    return bool((getattr(settings, "GITHUB_API_TOKEN", "") or "").strip())


def parse_calendar(body):
    if not isinstance(body, dict) or body.get("errors"):
        raise ValueError("GraphQL failure")
    weeks = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    if not isinstance(weeks, list) or len(weeks) > 54:
        raise ValueError("Invalid calendar")
    days = {}
    for week in weeks:
        entries = week["contributionDays"]
        if not isinstance(entries, list) or len(entries) > 7:
            raise ValueError("Invalid week")
        for entry in entries:
            day, count = entry["date"], entry["contributionCount"]
            if (not isinstance(day, str) or date.fromisoformat(day).isoformat() != day
                    or type(count) is not int or count < 0 or day in days):
                raise ValueError("Invalid day")
            days[day] = count
    if len(days) > 366:
        raise ValueError("Calendar exceeds one year")
    return [{"date": day, "count": days[day]} for day in sorted(days)]


def fetch_calendar(username):
    """Return validated daily counts, or None for any external-service failure."""
    if not configured() or not isinstance(username, str) or not USERNAME.fullmatch(username):
        return None
    request = urllib.request.Request(
        GRAPHQL_URL, data=json.dumps({"query": QUERY, "variables": {"login": username}}).encode(),
        headers={"Authorization": f"Bearer {settings.GITHUB_API_TOKEN.strip()}",
                 "Content-Type": "application/json", "User-Agent": "SpaceWorks"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Calendar response too large")
        return parse_calendar(json.loads(raw))
    except Exception:
        # Provider errors may contain credentials or a private body. Neither the
        # exception text, URL, username nor response body belongs in our log.
        logger.warning("public_profile.github_fetch_failed", extra={"provider": "github"})
        return None


ID_QUERY = "query($login: String!) { user(login: $login) { databaseId } }"


def fetch_database_id(username):
    """The immutable numeric GitHub account id behind a login, or None (unknown / any failure)."""
    if not configured() or not isinstance(username, str) or not USERNAME.fullmatch(username):
        return None
    request = urllib.request.Request(
        GRAPHQL_URL, data=json.dumps({"query": ID_QUERY, "variables": {"login": username}}).encode(),
        headers={"Authorization": f"Bearer {settings.GITHUB_API_TOKEN.strip()}",
                 "Content-Type": "application/json", "User-Agent": "SpaceWorks"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        body = json.loads(raw) if len(raw) <= MAX_RESPONSE_BYTES else {}
        value = body["data"]["user"]["databaseId"]
        return value if type(value) is int and value > 0 else None
    except Exception:
        logger.warning("public_profile.github_id_fetch_failed", extra={"provider": "github"})
        return None
