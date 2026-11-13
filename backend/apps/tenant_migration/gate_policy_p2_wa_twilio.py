"""Twilio signature ingress participates in the ordinary tenant source gate."""

HTTP_ANONYMOUS_PARTICIPANTS = {
    "apps.integrations.notification_wa_twilio_views.TwilioWhatsAppWebhookView.post": (
        "Signed tenant/generation URL resolves one makerspace; proof, consent, window and "
        "delivery changes run under tenant_write and the scoped PII write fence."
    ),
}
