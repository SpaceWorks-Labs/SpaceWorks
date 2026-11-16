"""Calendar refresh composed into the already scheduled GitHub task."""
from apps.operations.cloud_jobs import bounded


import logging

from apps.tenant_migration.gate_runtime import fanout_tenant_write

from .models_account_profile import AccountProfile
from .profile_github import refresh_calendar
from .profile_github_fetch import configured

logger = logging.getLogger(__name__)


def refresh_public_calendars():
    if not configured():
        return
    from .profile_images import home_space

    profiles = AccountProfile.objects.filter(is_visible=True, show_activity_graph=True).exclude(
        github_username="").select_related("user").order_by("pk")
    counts = {"skipped": 0}
    for profile in bounded.page(profiles, "github-calendars"):
        space = home_space(profile.user)
        if space is None:
            continue
        claim_id, makerspace_id = profile.pk, space.pk
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
            logger.warning("public_profile.github_refresh_failed", extra={"profile_id": claim_id})
