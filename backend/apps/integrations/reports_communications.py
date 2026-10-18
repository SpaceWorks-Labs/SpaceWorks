"""Compatibility entry point for the canonical communications report."""


def build_communications_health(makerspace_id, *, limit=None, date_range=None, grain="day"):
    from apps.operations.reports_communications import build_communications_health as build
    return build(makerspace_id, limit=limit, date_range=date_range, grain=grain)
