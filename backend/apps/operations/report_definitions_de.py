"""Phase 1f D/E analytical reports; subject exports keep their existing contracts."""

from apps.accounts import rbac
from .org_report_aggregate import register_combine
from .org_report_de import combine_feedback, combine_funnel, combine_revenue, combine_signups, combine_utilization
from .report_types import ReportDefinition
from .report_fields_de import (
    OCCUPANCY_FIELDS, LEAD_FIELDS, MEMBER_FIELDS, SIGNUP_FIELDS, FUNNEL_FIELDS,
    CHECKIN_FIELDS, FEEDBACK_FIELDS, REVENUE_FIELDS,
)
from .reports_de_common import chart

GRAINS = ("day", "week", "month")


def _definition(key, module, builder, fields, hint, spec, *, identity=False, grains=GRAINS):
    return ReportDefinition(
        key, f"apps.operations.{builder}", fields if identity else ("makerspace_id", *fields), (module,),
        required_action=rbac.Action.MANAGE_BOOKINGS if module == "bookings" else rbac.Action.MANAGE_EVENTS,
        title=key.replace("-", " ").title(), chart_hint=hint, grains=grains,
        identity_bearing=identity, deployment_aggregate=not identity, schedulable=not identity,
        chart_spec=spec,
    )


DE_REPORT_DEFINITIONS = (
    _definition("booking-occupancy", "bookings", "reports_booking_analytics.build_booking_occupancy", OCCUPANCY_FIELDS,
                "heatmap", chart("hour", (("occupancy_percent", "percent"),), series=("period", "weekday"))),
    _definition("booking-lead-time", "bookings", "reports_booking_analytics.build_booking_lead_time", LEAD_FIELDS,
                "histogram", chart("lead_time_bucket", (("booking_count", "reservations"),), series=("period",))),
    _definition("booking-top-members", "bookings", "reports_booking_analytics.build_booking_top_members", MEMBER_FIELDS,
                "bar", chart("member", (("booking_count", "reservations"),), top=10, tenant=False), identity=True, grains=()),
    _definition("event-signups", "events", "reports_event_analytics.build_event_signups", SIGNUP_FIELDS,
                "line", chart("period", (("cumulative_registrations", "registrations"),), series=("event_id", "title"), time=True)),
    _definition("event-revenue", "events", "reports_event_revenue.build_event_revenue", REVENUE_FIELDS,
                "bar", chart("period", (("net_amount", "currency_major"), ("promo_discount_amount", "currency_major")),
                             series=("makerspace_id", "event_id", "title"), time=True, currency=True, negatives=True)),
    _definition("event-funnel", "events", "reports_event_analytics.build_event_funnel", FUNNEL_FIELDS,
                "funnel", chart("period", (("registrations", "registrations"), ("confirmed", "registrations"),
                                           ("attended", "registrations")), series=("event_id", "title"), time=True)),
    _definition("event-checkin-times", "events", "reports_event_quality.build_event_checkin_times", CHECKIN_FIELDS,
                "histogram", chart("timing_bucket", (("checkin_count", "attendees"),), series=("period", "event_id"))),
    _definition("event-feedback-scores", "events", "reports_event_quality.build_event_feedback_scores", FEEDBACK_FIELDS,
                "bar", chart("title", (("average_score", "score"),), series=("period", "event_id", "question_id"), negatives=True)),
)

register_combine("booking-utilization", combine_utilization)
register_combine("event-signups", combine_signups)
register_combine("event-revenue", combine_revenue)
register_combine("event-funnel", combine_funnel)
register_combine("event-feedback-scores", combine_feedback)
