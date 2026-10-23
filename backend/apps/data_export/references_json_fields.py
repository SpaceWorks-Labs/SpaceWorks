"""Reviewed JSON fields whose embedded reference semantics need declarations."""

from apps.tenant_migration.catalog_events_programme_json import JSON_FIELDS as PROGRAMME_JSON_FIELDS

from apps.tenant_migration.catalog_reimbursements import JSON_FIELDS as REIMBURSEMENT_JSON_FIELDS

JSON_REFERENCE_FIELDS = PROGRAMME_JSON_FIELDS | REIMBURSEMENT_JSON_FIELDS | frozenset(
    {
        # Channel enum names carry no destination, endpoint or account identifiers.
        ("notifications.NotificationPreference", "channels"),
        ("apiclients.ApiClient", "scopes"),
        ("apiclients.ApiClient", "allowed_origins"),
        ("apiclients.ApiKeyRequest", "allowed_origins"),
        ("audit.AuditLog", "meta"),
        ("makerspaces.MakerspaceMembership", "witnessed_actor_snapshot"),
        ("makerspaces.MakerspaceMembership", "verified_actor_snapshot"),
        ("makerspaces.MakerspaceMembership", "activated_actor_snapshot"),
        ("makerspaces.MakerspaceMembership", "revoked_actor_snapshot"),
        # Allowlisted scalars only (devices.services_events.ALLOWED_DETAIL_KEYS); no
        # live reference of any kind.
        ("devices.DeviceEvent", "details"),
        ("bookings.BookableSpace", "custom_form"),
        # Booking pass geometry and four fixed field names; no identifiers or PII.
        ("bookings.BookableSpace", "pass_template"),
        ("bookings.Booking", "custom_answers"),
        # Reservation-status enum strings select recipients; no account references.
        ("bookings.BookingBroadcast", "statuses"),
        ("events.Event", "custom_form"),
        # Public tag strings are discovery labels, never model identifiers.
        ("events.Event", "tags"),
        # Curated venue scalars and layout enum strings/booleans, never model IDs.
        ("events.EventPage", "venue"),
        ("events.EventPage", "editorial_document"),
        ("events.EventPageRevision", "document"),
        ("makerspaces.MakerspacePublicPageRevision", "document"),
        # Organization revisions are deployment-only omitted models, outside
        # the tenant export JSON registry; their links use typed reference rows.
        ("events.EventPage", "section_order"),
        ("events.EventPage", "section_enabled"),
        ("events.EventPageSection", "options"),
        ("events.Event", "badge_template"),
        # Fixed layout scalars, never recipient identity. Artwork keys in issuance
        # snapshots are remapped separately by tenant_migration.object_fields.
        ("events.EventCertificateTemplateRevision", "parameters"),
        ("events.EventAttendanceCertificate", "layout_snapshot"),
        ("events.Event", "series_override_fields"),
        # Registration status enum labels filter recipients; no account identifiers.
        ("events.EventBroadcast", "statuses"),
        ("events.EventSeries", "custom_form"),
        ("events.EventFeedbackSurvey", "questions"),
        ("events.EventFeedbackSurvey", "answered_question_ids"),
        ("hardware_requests.PublicToolLoan", "asset_ids"),
        ("hardware_requests.PublicToolLoan", "qr_ids"),
        ("machines.Machine", "service_file_policy"),
        ("machines.Machine", "type_payload"),
        ("machines.MachineServiceRequest", "capability_payload"),
        ("machines.MachineType", "capability_config"),
        ("makerspaces.Makerspace", "cors_allowed_origins"),
        ("makerspaces.Makerspace", "website_embed_origins"),
        ("makerspaces.Makerspace", "enabled_modules"),
        ("makerspaces.Makerspace", "enabled_features"),
        ("makerspaces.Makerspace", "resource_limit_overrides"),
        ("makerspaces.Makerspace", "theme_config"),
        ("makerspaces.Makerspace", "branding_config"),
        ("makerspaces.Makerspace", "presence_preset_minutes"),
        # Validated integer hour offsets; no account or object identifiers.
        ("makerspaces.Makerspace", "booking_reminder_lead_hours"),
        ("makerspaces.Makerspace", "event_reminder_lead_hours"),
        ("makerspaces.MakerspaceLoanPolicy", "loan_reminder_offsets_hours"),
        # Strict weekday/date/time schema; no account or object references.
        ("makerspaces.Makerspace", "opening_hours"),
        ("makerspaces.MakerspaceRole", "granted_actions"),
        ("makerspaces.MakerspaceMembershipSettings", "application_schema"),
        ("makerspaces.MembershipRequest", "application_schema"),
        # Renewal automation stores bounded integer day offsets in JSON lists.
        ("makerspaces.MembershipPlan", "reminder_days_before"),
        ("makerspaces.MembershipPlan", "reminder_days_after"),
        ("makerspaces.MemberProfile", "domains"),
        ("makerspaces.MemberProfile", "skills"),
        ("makerspaces.MemberProfile", "links"),
        ("makerspaces.MemberProject", "tags"),
        ("makerspaces.MemberProfile", "interests"),
        ("makerspaces.MemberProfile", "languages"),
        ("makerspaces.MemberProfile", "education"),
        ("makerspaces.MemberProject", "links"),
        # Bounded integer day offsets; no embedded account or object references.
        ("payments.MakerspaceBillingSettings", "reminder_days_before"),
        ("payments.MakerspaceBillingSettings", "account_codes"),
        ("payments.PaymentDocument", "issuer"),
        ("payments.PaymentDocument", "lines"),
        ("payments.PaymentDocument", "tax_breakdown"),
        ("payments.MakerspaceBillingSettings", "reminder_days_after"),
        # Policy windows, percent, fee and currency figures; no account or object references.
        ("payments.RefundCase", "policy_snapshot"),
        ("tenant_migration.ExternalTenantReference", "snapshot"),
    }
)

JSON_REFERENCE_FIELDS |= frozenset({("integrations.WhatsAppTemplateBinding", "parameters"), ("integrations.MessagingConsent", "lifted_suppression_id")})

# Canonical notification runtime models (ChannelConfiguration, NotificationEnvelope,
# NotificationCutover, WhatsAppTemplate) are omitted from tenant artifacts, so their
# JSON payloads are never exported and need no reference declaration here; the
# guard compares this registry against JSON fields on EXPORTED models only.
