"""#180 S14: the "pushes after the stage deadline" signal, informational only (decision #8).

The existing GitHub check already runs for every stage snapshot (each is its own snapshot). Once a
snapshot's stage has closed, one more look asks GitHub for a commit after that stage's deadline plus
grace; a hit becomes an integrity flag (``github_push_after_stage_deadline``). It never changes
eligibility, triage or state, exactly like the early-commit flag.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)
RULE = "github_push_after_stage_deadline"


def github_since_url(repo_url, since):
    from urllib.parse import urlencode
    from .integrity import github_request_url
    base = github_request_url(repo_url, since).split("?", 1)[0]
    return base + "?" + urlencode({"per_page": 1, "since": since.isoformat()})


def check_after(*, repo_url, deadline, http):
    from .errors import SubmissionError
    try:
        response = http.get_json(github_since_url(repo_url, deadline), allowed_host="api.github.com",
                                 timeout_seconds=3, max_bytes=65536, allow_redirects=False)
    except Exception as exc:
        raise SubmissionError("integrity_provider_unavailable", 503) from exc
    if not isinstance(response, list) or len(response) > 1:
        raise SubmissionError("integrity_provider_unavailable", 503)
    if not response:
        return None
    sha = response[0].get("sha") if isinstance(response[0], dict) else None
    if not isinstance(sha, str) or len(sha) != 40:
        raise SubmissionError("integrity_provider_unavailable", 503)
    return {"rule_key": RULE, "commit_sha": sha}


def due_checks(space, now, limit=20):
    """Finished first checks whose stage has closed and whose push signal is not yet read."""
    from apps.events.models_r2_l2 import SubmissionIntegrityCheck
    from .stage_runtime import base_cutoff
    rows = (SubmissionIntegrityCheck.objects.filter(makerspace=space, after_deadline_state="",
                                                    state__in=("clear", "flagged", "no_repository"),
                                                    snapshot__stage_ref__isnull=False)
            .select_related("snapshot__stage_ref__stage", "event").order_by("pk")[:200])
    picked = []
    for row in rows:
        stage = row.snapshot.stage_ref.stage
        if now > base_cutoff(stage, row.event):
            picked.append((row, base_cutoff(stage, row.event)))
        if len(picked) >= limit:
            break
    return picked


def sweep_after_deadline(space, now=None):
    """Network first, then one short write per check; a provider outage leaves it for the next sweep."""
    from apps.events.models_r2_l2 import SubmissionIntegrityCheck
    from apps.events.services_write_boundary import write_boundary
    from .errors import SubmissionError
    from .integrity import record_flag_locked
    from .integrity_http import GitHubHttp
    from .pii import prepare_documents
    now = now or timezone.now()
    done = 0
    for check, deadline in due_checks(space, now):
        links = list(check.snapshot.link_refs.filter(kind="repo", provider="github").order_by("pk")[:3])
        state, evidence = ("no_repository", None) if not links else ("clear", None)
        try:
            for link in links:
                evidence = check_after(repo_url=link.url, deadline=deadline, http=GitHubHttp())
                if evidence:
                    state = "flagged"
                    break
        except SubmissionError:
            logger.warning("submission_push_signal_unavailable", extra={"check_id": check.pk})
            continue
        with prepare_documents(check.event_id), write_boundary(check.event):
            row = SubmissionIntegrityCheck.objects.select_for_update().get(pk=check.pk)
            row.after_deadline_state = state
            row.save(update_fields=["after_deadline_state"])
            if evidence:
                record_flag_locked(actor=None, event=check.event, snapshot=check.snapshot, evidence=evidence)
        done += 1
    return done
