"""Periodic makerspace tasks."""
from apps.operations.cloud_jobs import bounded


from celery import shared_task

from apps.tenant_migration.gate_runtime import fanout_tenant_write


@shared_task(name="apps.makerspaces.tasks.cleanup_public_page_assets_task")
def cleanup_public_page_assets_task():
    from .public_page_asset_cleanup import sweep
    return sweep()


@shared_task(name="apps.makerspaces.tasks.verify_github_ownership_task", soft_time_limit=30, time_limit=45)
def verify_github_ownership_task(user_id):
    """Verify one account's GitHub username against its linked sign-in, then fetch its calendar (decision 338).

    Queued on commit after a GitHub sign-in is linked or the username is saved. It reads the account's own
    profile and writes only disposable cache entries, so it holds no tenant gate.
    """
    from django.contrib.auth import get_user_model

    from .models_account_profile import AccountProfile
    from .profile_github import refresh_calendar, verify_ownership
    from .public_profile_cache import invalidate_account

    profile = AccountProfile.objects.filter(user_id=user_id).exclude(github_username="").first()
    if profile is None or not get_user_model().objects.filter(pk=user_id, is_active=True).exists():
        return {"verified": False}
    verified = verify_ownership(profile)
    if verified:
        refresh_calendar(profile.pk)
    invalidate_account(user_id)
    return {"verified": bool(verified)}


@shared_task(name="apps.makerspaces.tasks.refresh_github_contributions_task")
def refresh_github_contributions_task():
    """Refresh the cached GitHub contribution counts on maker profiles.

    Scheduled rather than fetched on read, so a slow or rate-limited GitHub can never
    make a profile page slow and can never make it fail. Dormant when
    `GITHUB_API_TOKEN` is unset: nothing is called and every count stays None.
    """
    from apps.makerspaces import github_contributions
    from apps.makerspaces.models import AccountProfile

    if not github_contributions.is_configured():
        return {"configured": False}
    counts = {"updated": 0, "unavailable": 0, "skipped": 0}
    from apps.makerspaces.scheduled_scope import live_space_ids
    # Maker profiles belong to the membership module: none refresh while it is off.
    from apps.makerspaces.profile_images import home_space

    live = set(live_space_ids("membership"))
    profiles = AccountProfile.objects.select_related("user").exclude(github_username="")
    for profile in bounded.page(profiles, "github-profiles"):
        if not github_contributions.due_for_sync(profile):
            continue
        space = home_space(profile.user)
        if space is None or space.pk not in live:
            continue
        # `refresh` swallows every failure and keeps the last known count, so one bad
        # handle cannot stop the rest of the run.
        with fanout_tenant_write(
            space.pk,
            operation="github_contributions_refresh",
            counts=counts,
        ) as should_process:
            if not should_process:
                continue
            if github_contributions.refresh(profile):
                counts["updated"] += 1
            else:
                counts["unavailable"] += 1
    from .profile_github_tasks import refresh_public_calendars
    refresh_public_calendars()
    return {"configured": True, **counts}


# Celery autodiscovery imports only `tasks.py`; import the sibling so the worker
# registers the kiosk lease cleanup task named in CELERY_BEAT_SCHEDULE.
from apps.makerspaces import tasks_station  # noqa: E402,F401
