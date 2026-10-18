"""Messaging history/configuration disclosure was reviewed independently of the rail."""
EXPORTED_FIELDS = {
    "integrations.WhatsAppTemplateBinding": "id makerspace feature event audience business_account_id template_name language parameters is_active needs_review",
    "integrations.MessagingConsent": "id makerspace user channel action phone_e164 phone_verified_at source lifted_suppression_id created_at",
}
OMITTED_MODELS = {
    "integrations.PlatformWhatsAppSettings": "Deployment-wide provider credentials never travel.",
    "integrations.MakerspaceMessagingSettings": "Provider credentials, sender reservation and callback verification are re-established on the target.",
    "integrations.MessagingSenderIdentity": "Deployment-local unique provider reservation and callback ownership.",
    "integrations.MessagingSenderCredential": "Encrypted provider callback credentials and retired credential history.",
    "integrations.MessagingSuppression": "Deployment-keyed sender protection, retained without portable recipient identity.",
    "integrations.MessagingRecipientAlias": "Deployment-keyed provider identity correlation; never portable.",
    "integrations.MessagingRecipientCorrelation": "Deployment-local send barrier, never portable authority.",
    "integrations.MessagingDelivery": "Runtime provider delivery telemetry; personal export uses an explicit allowlist.",
    "integrations.MessagingWebhookEvent": "Deployment-local webhook replay and processing state.",
}
