"""Release 2 r2-superadmin-controls (#185, #187A): source-gate declarations.

The space controls are lifecycle governance, excluded from source quiescence exactly like
archive and purge (they must work on the very space they pause). The hosting-invoice
callbacks settle the platform's own invoices under ``tenant_write`` of the invoice's space,
permitted in every state. The beat tasks write platform governance rows only.
"""

from apps.space_controls.write_policy import CONTROL_ROUTES

_CONTROL = "Superadmin space control (#185): lifecycle governance, excluded like archive and purge."
HTTP_EXEMPTIONS = {name: _CONTROL for name in CONTROL_ROUTES}

HTTP_ANONYMOUS_PARTICIPANTS = {
    f"apps.managed_hosting.views_space.{view}.post": (
        "Signed provider callback for a platform hosting invoice; settlement commits under tenant_write "
        "of the invoice's space (permitted in every state: money a payer sent must settle)."
    )
    for view in ("StripeHostingCallbackView", "RazorpayHostingCallbackView")
}

ADMIN_ACTION_EXEMPTIONS = {
    f"makerspaces.Makerspace.{action}": _CONTROL
    for action in ("suspend_makerspaces", "unsuspend_makerspaces", "read_only_makerspaces",
                   "lift_read_only_makerspaces", "cancel_makerspace_schedules")
}

TASKS = {
    "apps.space_controls.tasks.run_space_schedules_task": (
        "Scheduled archive and purge run the express lifecycle exclusions; reminders are platform mail."
    ),
    "apps.space_controls.tasks.send_announcement_emails_task": (
        "Platform announcements: platform rows and platform mail only, no tenant writes."
    ),
    "apps.managed_hosting.tasks.sweep_managed_hosting_task": (
        "Managed-hosting trials and billing: platform rows; read-only is a space-control lifecycle step."
    ),
}


def gate_tasks(exemptions):
    exemptions.update(TASKS)
