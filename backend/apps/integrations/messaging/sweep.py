"""Compatibility recovery entry point; never scans legacy delivery rows for sending."""


def run_sweep():
    from apps.integrations.notification_ingress import recover
    return recover()
