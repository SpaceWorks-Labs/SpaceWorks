"""The monthly staff membership summary (X33): a scheduled-report preset with opt-outs.

Behind `membership.monthly_summary`. Turning the preset on creates (or reactivates) ONE
monthly `ReportSchedule` of `membership-monthly-summary`, created by the Space Manager
who turned it on and addressed to everyone holding `manage_members`; the ordinary
scheduled-report delivery sends it. It is a membership setting, so the switch goes
through `assert_setting_write` (Space Manager only). Any recipient opts themselves out
(`MembershipSummaryOptOut`) and back in. While the switch is off the schedule is
skipped by the scheduler (`feature_disabled`), and nothing is lost.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import MembershipSummaryOptOut

REPORT_KEY = "membership-monthly-summary"
SETTING_KEY = "membership.monthly_summary_schedule"


def schedule_for(makerspace):
    from apps.operations.models_report_schedules import ReportSchedule
    return ReportSchedule.objects.filter(makerspace=makerspace, report_key=REPORT_KEY).order_by("pk").first()


def opted_out_user_ids(schedule):
    if schedule.report_key != REPORT_KEY:
        return frozenset()
    return frozenset(MembershipSummaryOptOut.objects.filter(makerspace_id=schedule.makerspace_id)
                     .values_list("user_id", flat=True))


def status(actor, makerspace):
    row = schedule_for(makerspace)
    return {"enabled": bool(row and row.is_active), "next_run_at": row.next_run_at if row else None,
            "opted_out": MembershipSummaryOptOut.objects.filter(makerspace=makerspace, user=actor).exists()}


def _first_of_next_month(makerspace):
    from apps.makerspaces.local_time import local_day_bounds, to_local
    today = to_local(makerspace, timezone.now()).date()
    following = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    return local_day_bounds(makerspace, following)[0] + timedelta(hours=8)


def set_enabled(actor, makerspace, enabled):
    from apps.makerspaces.settings_authority import assert_setting_write, record_change
    from apps.operations.models_report_schedules import ReportSchedule
    decision = assert_setting_write(actor, makerspace, "membership", SETTING_KEY)
    with transaction.atomic():
        space = require_membership_feature_locked(makerspace.pk, "monthly_summary")
        row = schedule_for(space)
        before = bool(row and row.is_active)
        if enabled and row is None:
            row = ReportSchedule.objects.create(
                makerspace=space, report_key=REPORT_KEY, grain="month", format=ReportSchedule.Format.CSV,
                cadence=ReportSchedule.Cadence.MONTHLY, next_run_at=_first_of_next_month(space),
                recipient_actions=["manage_members"], created_by=actor)
            audit.record(actor, "report_schedule.created", makerspace=space, target=row,
                         meta={"schedule_id": row.pk, "report_key": REPORT_KEY})
        elif row is not None and row.is_active != enabled:
            row.is_active = enabled
            if enabled:
                row.created_by = actor
                row.next_run_at = _first_of_next_month(space)
            row.save(update_fields=["is_active", "created_by", "next_run_at", "updated_at"])
            audit.record(actor, "report_schedule.updated", makerspace=space, target=row,
                         meta={"schedule_id": row.pk, "report_key": REPORT_KEY})
        record_change(actor, space, "membership", SETTING_KEY, before, enabled, decision)
    return status(actor, makerspace)


def set_opt_out(actor, makerspace, opted_out):
    with transaction.atomic():
        space = require_membership_feature_locked(makerspace.pk, "monthly_summary")
        if opted_out:
            _row, created = MembershipSummaryOptOut.objects.get_or_create(makerspace=space, user=actor)
        else:
            created = bool(MembershipSummaryOptOut.objects.filter(makerspace=space, user=actor).delete()[0])
        if created and opted_out:
            audit.record(actor, "membership.summary_opted_out", makerspace=space, target=space,
                         meta={"user_id": actor.pk})
        elif created:
            audit.record(actor, "membership.summary_opted_in", makerspace=space, target=space,
                         meta={"user_id": actor.pk})
    return status(actor, makerspace)
