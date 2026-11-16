"""Optional informational GitHub history signal. Never changes eligibility/state."""
from urllib.parse import urlsplit

from django.utils.dateparse import parse_datetime
from django.utils import timezone

from apps.audit.services import record
from .errors import SubmissionError
from .models_projects import SubmissionIntegrityFlag
from .links import normalize_link


def github_request_url(repo_url, kickoff):
    normalized, provider = normalize_link(repo_url, "repo")
    parts = urlsplit(normalized)
    path = parts.path.strip("/").split("/")
    if provider != "github" or parts.hostname != "github.com" or len(path) != 2:
        raise SubmissionError("invalid_github_repository")
    import re
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", item) or item in {".", ".."} for item in path):
        raise SubmissionError("invalid_github_repository")
    from urllib.parse import urlencode
    return f"https://api.github.com/repos/{path[0]}/{path[1].removesuffix('.git')}/commits?" + urlencode(
        {"per_page": 1, "until": kickoff.isoformat()})


def check_github(*, repo_url, kickoff, enabled, http):
    if not enabled:
        return None
    # G's outbound adapter pins api.github.com, disallows redirects and private
    # resolved addresses, imposes response byte cap and rate/timeout backoff.
    url = github_request_url(repo_url, kickoff)
    try:
        response = http.get_json(url, allowed_host="api.github.com", timeout_seconds=3,
                                 max_bytes=65536, allow_redirects=False)
    except Exception as exc:
        raise SubmissionError("integrity_provider_unavailable", 503) from exc
    if not isinstance(response, list) or len(response) > 1:
        raise SubmissionError("integrity_provider_unavailable", 503)
    if not response:
        return None
    try:
        at = parse_datetime(response[0]["commit"]["committer"]["date"])
        sha = response[0]["sha"]
        if at is None or timezone.is_naive(at) or not __import__("re").fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise SubmissionError("integrity_provider_unavailable", 503) from exc
    return {"rule_key": "github_commit_before_kickoff", "commit_sha": sha} if at < kickoff else None


def record_flag_locked(*, actor, event, snapshot, evidence):
    if evidence is None:
        return None
    flag, created = SubmissionIntegrityFlag.objects.get_or_create(snapshot=snapshot,
        rule_key=evidence["rule_key"], defaults={"evidence": {"commit_sha": evidence["commit_sha"]}})
    if not created:
        return flag
    record(actor, "event.submission_integrity_flagged", makerspace=event.makerspace, target=flag,
           meta={"snapshot_id": snapshot.pk, "rule_key": flag.rule_key})
    return flag
