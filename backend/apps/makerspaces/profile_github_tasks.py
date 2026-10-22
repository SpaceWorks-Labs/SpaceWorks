"""Calendar refresh composed into the already scheduled GitHub task."""
from apps.operations.cloud_jobs import bounded


import logging

from apps.tenant_migration.gate_runtime import fanout_tenant_write

from .models_profiles import PublicHandle
from .profile_github import refresh_calendar
from .profile_github_fetch import configured

logger = logging.getLogger(__name__)


def refresh_public_calendars():
    if not configured():
        return
    claims = PublicHandle.objects.filter(
        profile__public_visible=True, profile__show_activity_graph=True,
    ).exclude(profile__github_username="").values_list("pk", "profile__membership__makerspace_id")
    counts = {"skipped": 0}
    for claim_id, makerspace_id in bounded.page(claims, "github-calendars"):
        try:
            # Keep source migration's session fence across the external fetch, but
            # no database transaction/row lock across provider I/O.
            with fanout_tenant_write(makerspace_id, operation="github_contributions_refresh", counts=counts) as allowed:
                if not allowed:
                    continue
                bounded.check()
                refresh_calendar(claim_id)
                bounded.check()
        except Exception:
            logger.warning("public_profile.github_refresh_failed", extra={"claim_id": claim_id})
