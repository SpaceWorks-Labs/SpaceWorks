"""Typed Events adapter for the shared signed-read target resolver."""

from apps.apiclients.read_contract import ReadTarget, register_read_target


def register_targets():
    register_read_target("integration-event-list", ReadTarget())
    register_read_target("integration-event-detail", ReadTarget("events.Event"))
    register_read_target("integration-event-participants", ReadTarget("events.Event"))
    # Release 2 L6 (G35): ticket orders, tenant-bound by the order row.
    register_read_target("integration-order-list", ReadTarget())
    register_read_target("integration-order-detail", ReadTarget("events.EventOrder"))
