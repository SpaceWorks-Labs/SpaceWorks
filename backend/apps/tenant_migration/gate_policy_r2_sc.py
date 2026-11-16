"""Release 2 S-C: source-gate declaration for the login-security telemetry retention task."""


def gate_tasks(exemptions):
    exemptions.update({
        "apps.accounts.tasks_login_security.purge_login_security_task": (
            "Platform-global IP auto-block and django-axes telemetry retention (OMITTED/EMPTY rows); "
            "no tenant writes."
        ),
    })
