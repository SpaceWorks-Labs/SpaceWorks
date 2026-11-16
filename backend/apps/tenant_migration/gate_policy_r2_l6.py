"""Release 2 L6: source-gate declarations for the order checkout sweep and invite updates."""


def gate_tasks(internal, resolvers):
    resolvers.update({
        # One event's updated calendar invites; the event row names its space.
        "apps.events.tasks_invites.send_invite_updates_task": ("events.Event", 0, "makerspace_id"),
    })
    internal.update({
        "apps.events.reminders_payments.sweep_order_checkouts_task": (
            "Each order expiry, settlement retry and reminder runs inside that order's own event write "
            "boundary, which holds its space's source gate."
        ),
    })
