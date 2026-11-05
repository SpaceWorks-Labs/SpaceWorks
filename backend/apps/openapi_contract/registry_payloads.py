"""Payloads whose shape SpaceWorks does not own, and success responses with no body.

FREE_FORM: a request or response defined by someone else -- a payment provider's event,
a chat platform's callback, Apple's Wallet web-service protocol, a government return
format. There is no serializer to point at; the reason says whose shape it is. The schema
stamps `x-free-form`, and the guard accepts an untyped body only where it is stamped.

EMPTY_SUCCESS: a success that answers with headers or status alone (a provider ack, a
"code sent" 202). The schema stamps `x-response-body: none`.

Keys are `module.Class` and the HTTP method.
"""

_STRIPE = "A Stripe event object, verified by its Stripe-Signature header."
_TWILIO = "Twilio's form-encoded callback, verified by its X-Twilio-Signature header."
_META = "Meta's WhatsApp Cloud API webhook payload, verified by X-Hub-Signature-256."
_CHAT = "The chat platform's interaction callback (Slack, Discord or Mattermost), signature-verified."
_APPLE = "Apple Wallet web-service protocol (developer.apple.com/documentation/walletpasses)."

FREE_FORM = {
    ("apps.payments.views.StripeWebhookView", "POST"): {"request": _STRIPE},
    ("apps.payments.views.RazorpayWebhookView", "POST"): {
        "request": "A Razorpay webhook event, verified by its X-Razorpay-Signature header."},
    ("apps.payments_rail.views_connect.StripeConnectWebhookView", "POST"): {"request": _STRIPE},
    ("apps.integrations.notification_slack_views.ChatInboundView", "POST"): {
        "request": _CHAT, "response": "The platform-specific acknowledgement (for example a challenge echo)."},
    ("apps.integrations.views_messaging_webhooks.TwilioMessagingWebhookView", "POST"): {
        "request": _TWILIO, "response": "An empty TwiML acknowledgement."},
    ("apps.integrations.views_messaging_webhooks.MetaMessagingWebhookView", "POST"): {
        "request": _META, "response": "An acknowledgement."},
    ("apps.card_designs.wallet.views_apple.ApplePassRegistrationView", "POST"): {"request": _APPLE},
    ("apps.card_designs.wallet.views_apple.ApplePassLogView", "POST"): {"request": _APPLE},
    ("apps.card_designs.wallet.views_apple.ApplePassSerialsView", "GET"): {"response": _APPLE},
    ("apps.events.contributions.views_completion.RoleOwnerExportView", "GET"): {
        "response": "The holder's own role record, as the forms module's owner export document."},
    ("apps.payments.views_tax.Gstr1JsonView", "GET"): {
        "response": "The GSTR-1 return in the GST portal's offline-tool JSON format."},
}

EMPTY_SUCCESS = {
    ("apps.integrations.views.TelegramWebhookView", "POST"): "Telegram callbacks are acknowledged and discarded.",
    ("apps.integrations.notification_wa_twilio_views.TwilioWhatsAppWebhookView", "POST"): "Provider ack.",
    ("apps.admin_api.views_hosting.TlsCheckView", "GET"): "The TLS on-demand ask: the status is the answer.",
    ("apps.card_designs.wallet.views_apple.ApplePassRegistrationView", "POST"): "Apple protocol: status only.",
    ("apps.card_designs.wallet.views_apple.ApplePassRegistrationView", "DELETE"): "Apple protocol: status only.",
    ("apps.card_designs.wallet.views_apple.ApplePassLogView", "POST"): "Apple protocol: status only.",
    ("apps.payments.donations.views_public.DonationEmailCodeView", "POST"): "202: the code was sent if possible.",
    ("apps.hardware_requests.public_contact_views.RequestContactCodeView", "POST"): "202: the code was sent if possible.",
}
