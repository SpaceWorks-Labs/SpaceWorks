"""Messaging history travels inert; provider credentials/protection remain local."""
PROJECTED_LABELS = frozenset({"integrations.WhatsAppTemplateBinding", "integrations.MessagingConsent"})


def authority_entries(authority, disposition):
    return tuple((edge, authority(disposition.RESET, "Imported communication history never authorizes target sending.")) for edge in (
        ("integrations.MessagingConsent", "action"),
        ("integrations.MessagingConsent", "lifted_suppression_id"),
        ("integrations.MessagingConsent", "sender_key"),
        ("integrations.MessagingConsent", "configuration_generation"),
        ("integrations.MessagingConsent", "endpoint"),
        ("integrations.WhatsAppTemplateBinding", "is_active"),
        ("integrations.WhatsAppTemplateBinding", "needs_review"),
    ))


def projections(field):
    reason = "Target members and operators must re-establish addressed sending authority."
    return {
        ("integrations.MessagingConsent", "action"): field("opted_out", reason=reason),
        ("integrations.MessagingConsent", "sender_key"): field("", reason=reason),
        ("integrations.MessagingConsent", "configuration_generation"): field(0, reason=reason),
        ("integrations.MessagingConsent", "endpoint"): field(None, reason=reason),
        ("integrations.MessagingConsent", "lifted_suppression_id"): field([], reason=reason),
        ("integrations.WhatsAppTemplateBinding", "is_active"): field(False, reason=reason),
        ("integrations.WhatsAppTemplateBinding", "needs_review"): field(True, reason=reason),
    }
