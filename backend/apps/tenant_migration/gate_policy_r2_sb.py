"""Release 2 S-B: source-gate declaration for the security-alert delivery task."""


def gate_tasks(exemptions):
    exemptions.update({
        "apps.accounts.tasks_security_alerts.deliver_security_alert_task": (
            "Platform security-alert mail for one account (OMITTED/EMPTY SecurityAlert rows); "
            "no tenant writes."
        ),
    })
