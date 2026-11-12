"""Platform roll-up of the global profile and username namespace (decisions 302-305).

Profiles and handles belong to the ACCOUNT, not to a makerspace, so this is a deployment-only
report: counts of accounts, profiles, public profiles and claimed handles. It has no makerspace
dimension and carries no handle, name or contact, so it cannot disclose any one person.
"""

from datetime import timedelta

from django.utils import timezone

from apps.operations.report_types import ReportResult
from apps.operations.reports_j_common import calendar_range

FIELDS = ("makerspace_id", "metric", "value")


def build_platform_profile_adoption(makerspace_id=None, *, platform_context=None, limit=None, date_range=None,
                                    grain=None, actor=None):
    from apps.accounts.models import User
    from apps.makerspaces.models import AccountProfile, PublicHandle
    now = timezone.now()
    start, end = calendar_range(date_range) or (None, None)
    end = end or now
    start = start or end - timedelta(days=30)
    handles = PublicHandle.objects.filter(user__isnull=False)
    metrics = [
        ("accounts", User.objects.filter(is_active=True).count()),
        ("profiles", AccountProfile.objects.count()),
        ("profiles_visible_to_members", AccountProfile.objects.filter(is_visible=True).count()),
        ("profiles_public_on_web", AccountProfile.objects.filter(public_visible=True).count()),
        ("handles_claimed", handles.count()),
        ("handles_claimed_in_period", handles.filter(claimed_at__gte=start, claimed_at__lt=end).count()),
        ("handles_changed_in_period", handles.filter(changed_at__gte=start, changed_at__lt=end).count()),
        ("profiles_created_in_period", AccountProfile.objects.filter(created_at__gte=start, created_at__lt=end).count()),
    ]
    rows = [{"makerspace_id": None, "metric": metric, "value": value} for metric, value in metrics]
    return ReportResult(FIELDS, rows if limit is None else rows[:limit], {
        "definition": "Account-level profile and username adoption: counts only, no handle or person appears."})
