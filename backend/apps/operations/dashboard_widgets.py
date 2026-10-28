"""Action-driven dashboard projections of the canonical report service."""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.accounts import rbac
from apps.admin_api.permissions import active_user
from apps.makerspaces.local_time import to_local
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.servability import is_servable
from .report_registry import REPORT_REGISTRY


@dataclass(frozen=True)
class DashboardWidget:
    key: str
    title: str
    required_action: str
    required_modules: tuple[str, ...]
    kind: str
    report_keys: tuple[str, ...]
    default_period: int = 30


def _widget(key, kind, *, action=None, title=None):
    definition = REPORT_REGISTRY.get(key)
    if definition is None:  # Deployment tombstones remove their catalog entries.
        return None
    return DashboardWidget(
        key, title or definition.title, action or definition.required_action,
        ("reports", *definition.required_modules), kind, (key,),
    )


WIDGETS = tuple(widget for widget in (
    _widget("loan-throughput", "trend"),
    _widget("overdue-loans", "queue", action=rbac.Action.VIEW_INVENTORY),
    _widget("stock-health", "trend"),
    _widget("most-lent", "top_n"),
    _widget("qr-scans", "heatmap"),
    _widget("consumable-pools", "count"),
    _widget("machine-usage", "top_n"),
    _widget("machine-usage-heatmap", "heatmap"),
    _widget("machine-downtime", "trend"),
    _widget("service-queue-times", "trend"),
    _widget("machine-errors", "trend"),
    _widget("machine-service", "trend"),
    _widget("consumable-usage", "trend"),
    _widget("event-funnel", "trend"),
    _widget("booking-occupancy", "heatmap"),
    _widget("revenue-over-time", "trend"),
    _widget("membership-growth", "trend", action=rbac.Action.MANAGE_MEMBERS),
    _widget("communications-health", "trend"),
    _widget("mobile-devices", "trend", title="Mobile adoption"),
    _widget("top-borrowers", "top_n", action=rbac.Action.VIEW_INVENTORY),
    _widget("booking-top-members", "top_n"),
    _widget("machine-usage-members", "top_n"),
) if widget is not None)

LOAN_WIDGETS = {"loan-throughput", "overdue-loans", "most-lent", "top-borrowers", "stock-health"}


def visible_widgets(actor, makerspace):
    """Omit unauthorized data entirely."""
    if not active_user(actor) or not is_servable(makerspace) or rbac.is_handout_only(actor, makerspace.pk):
        return ()
    visible = []
    for widget in WIDGETS:
        definitions = [REPORT_REGISTRY[key] for key in widget.report_keys]
        actions = {widget.required_action, *(d.required_action for d in definitions)}
        if any(d.identity_bearing for d in definitions):
            actions.add(rbac.Action.VIEW_AUDIT)
        if any(not rbac.can(actor, action, makerspace.pk) for action in actions):
            continue
        modules = set(widget.required_modules) | {module for d in definitions for module in d.required_modules}
        if not all(module_enabled(makerspace, module) for module in modules):
            continue
        if any(not d.required_modules and d.section_modules
               and not any(module_enabled(makerspace, module) for module in d.section_modules)
               for d in definitions):
            continue
        if widget.key in LOAN_WIDGETS and not feature_enabled(makerspace, "loans.enabled"):
            continue
        if any(d.required_feature and not feature_enabled(makerspace, d.required_feature) for d in definitions):
            continue
        if any(d.platform_only or d.subject_kind or not d.previewable for d in definitions):
            continue
        visible.append(widget)
    return tuple(visible)


def build_widgets(actor, makerspace):
    """Return authorized descriptors; clients fetch each report independently.

    A dashboard request must not execute analytical builders before returning its
    operational counters. Report GETs recheck current actor/module/type scope.
    """
    today = to_local(makerspace, timezone.now()).date()
    result = []
    for widget in visible_widgets(actor, makerspace):
        definition = REPORT_REGISTRY[widget.report_keys[0]]
        result.append({
            "key": widget.key, "title": widget.title, "kind": widget.kind,
            "required_action": widget.required_action,
            "required_modules": list(widget.required_modules),
            "report_keys": list(widget.report_keys), "default_period": widget.default_period,
            "data": {"typed_rows": [], "meta": {"deferred": True,
                "start": (today - timedelta(days=widget.default_period - 1)).isoformat(),
                "end": today.isoformat()}},
            "chart_spec": definition.chart_spec,
        })
    return result
