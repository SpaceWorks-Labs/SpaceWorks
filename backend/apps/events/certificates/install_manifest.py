"""G-owned startup/routes/registries consume these declarations while Events is active."""

MODEL_EXPORT_MODULE = "apps.events.certificates.model_exports"
URL_PROVIDERS = (
    ("admin/", "apps.events.credentials.urls_admin"),
    ("admin/", "apps.events.certificates.urls_admin"),
    ("admin/", "apps.events.certificates.urls_library"),
    ("member/", "apps.events.profile_photos.urls_member"),
    ("public/", "apps.events.profile_photos.urls_public"),
    ("public/", "apps.events.certificates.urls_public"),
)
PROVIDERS = {
    "online_credential_confirm": "apps.events.credentials.resolution.confirm",
    "credential_issue_locked": "apps.events.credentials.workflow.issue_locked",
    "credential_revoke_locked": "apps.events.credentials.workflow.revoke_locked",
    "credential_expire": "apps.events.credentials.workflow.expire",
    "public_member_card": "apps.events.profile_photos.projection.project_public",
    "certificate_eligibility_install": "apps.events.certificates.subjects.install_eligibility",
    "certificate_notification": "apps.events.certificates.notifications.certificate_envelope",
    "certificate_notification_eligibility": "apps.events.certificates.notifications.eligible",
    "certificate_document": "apps.events.certificates.notifications.document_for_recipient",
    "certificate_batch_resume": "apps.events.certificates.tasks.resume_batches",
    "certificate_render_resume": "apps.events.certificates.tasks.resume_certificates",
    "print_cleanup": "apps.events.certificates.print_cleanup.cleanup_expired",
    "profile_invalidated_jobs": "apps.events.certificates.print_policy.invalidate_profile",
    "artwork_catalogue_install": "apps.events.certificates.seeds.install_catalogue",
}
FRONTEND_PROVIDERS = {
    "/certificates/verify/:verificationId": "features/events/eventPresentation/CertificateVerificationPage",
    "after_checkin": "features/staff/eventCredentials/QuickPrintSheet",
    "bulk_certificates": "features/staff/eventCredentials/BulkCertificates",
}
RUNTIME_ONLY = True
BADGE_DOCUMENT_ATTACHMENTS = False
