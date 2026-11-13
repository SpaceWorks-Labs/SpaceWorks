"""Tenant-resolving chat callbacks; no exemption from source quiescence."""

HTTP_ANONYMOUS_PARTICIPANTS = {
    "apps.integrations.notification_slack_views.ChatInboundView.post": (
        "Path resolves a servable tenant; signed/token-authenticated callbacks acknowledge only and write nothing."
    ),
}
