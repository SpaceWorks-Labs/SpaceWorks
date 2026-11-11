"""Explicit source-gate http participation declarations."""

from .gate_policy_replay import REPLAY_HTTP_PARTICIPANTS
from .gate_policy_p2_wa_twilio import HTTP_ANONYMOUS_PARTICIPANTS as WA_TWILIO_PARTICIPANTS


# Signature ingress stays reachable while ordinary tenant mutations are frozen.
# The provider owner must commit durable receipts/sender STOP protection before
# acknowledging, and gate tenant status/proof writes inside the processor.
PROVIDER_INGRESS_ROUTES = frozenset({
    "messaging-twilio-platform-status", "messaging-twilio-platform-inbound",
    "messaging-twilio-status", "messaging-twilio-inbound", "messaging-meta-platform", "messaging-meta",
    "whatsapp-meta-webhook", "whatsapp-twilio-inbound", "whatsapp-twilio-status",
})
HTTP_EXEMPTIONS = {
    "notification-media": (
        "Single-use GET resolves its tenant from the hashed media grant, then takes "
        "tenant_write for atomic consumption and audit; closed source gates refuse disclosure."
    ),
    **{name: "Signed provider ingress durably records deployment events; status writes gate their resolved tenant; STOP protection must survive frozen tenants."
       for name in PROVIDER_INGRESS_ROUTES},
    "auth-account-restore-email": "Global identity recovery never reinstates tenant authority.",
    "auth-account-restore-phone": "Global identity recovery never reinstates tenant authority.",
    "auth-account-restore-social-start": "Global provider recovery intent has no tenant mutation.",
    "auth-account-restore-social-complete": "Global identity recovery never reinstates tenant authority.",
    "auth-account-deletion": "Global departure discovers and locks every owned tenant gate inside Stage A.",
    "auth-reauth": "Global browser session proof has no tenant-owned authority.",
    "auth-reauth-social-start": "Global session-bound credential intent.",
    "auth-reauth-social-complete": "Global credential verification and browser proof.",
    "auth-reauth-social-factor": "Global session-bound provider second-factor proof.",
    "auth-reauth-phone-start": "Global session-bound phone credential challenge.",
    "auth-reauth-phone-confirm": "Global phone credential verification and session proof.",
    "auth-reauth-enrollment-email": "Global session-bound MFA enrollment confirmation.",
    "auth-reauth-enrollment-confirm": "Global enrollment-only proof, never a tenant grant.",
    "control-reauthentication": "Global control session proof; existing control MFA gate remains.",
    "auth-organizations-self-service": "Global organization governance; creation confers no tenant authority.",
    "auth-me": "Phase 8 i18n: the account's own language preference is platform-global account data.",
    "admin-space-pack-profiles": (
        "Platform configuration snapshots have no tenant rows; applying one uses the target tenant gate."
    ),
    "tenant-migration-source-quiesce": (
        "A completed export has already quiesced the source; reasserting its fenced "
        "lease must remain reachable."
    ),
    "tenant-migration-export-download-url": (
        "The encrypted archive can only be downloaded after its export quiesces the source."
    ),
    "tenant-migration-source-archive": (
        "Source cutover must archive the tenant while its gate is quiesced."
    ),
    "tenant-migration-source-recover": (
        "Verified abort recovery must reopen a migrated-out source while its gate is closed."
    ),
    "backup-recovery-state": "Deployment recovery must be able to quarantine/recover the deployment.",
    "stripe-connect-webhook": "Connect account events are platform routing state, not one source tenant.",
    "telegram-webhook": (
        "Authenticate before opaque proof lookup. Private account linking resolves its tenant "
        "and consumes under notification_proofs.tenant_write; closed gates refuse linking. "
        "Other updates and every decision callback are acknowledged without writes."
    ),
    "auth-login": "Global user session state is excluded from tenant quiescence.",
    "auth-mfa": "Global MFA credential state is excluded from tenant quiescence.",
    "auth-mfa-enroll": "Global MFA enrollment state is excluded from tenant quiescence.",
    "auth-mfa-confirm": "Global MFA credential and session state is excluded from tenant quiescence.",
    "auth-mfa-verify": "Global MFA verification and session state is excluded from tenant quiescence.",
    "auth-mfa-recovery": "Global MFA recovery credentials are excluded from tenant quiescence.",
    "auth-mfa-disable": "Global MFA credential state is excluded from tenant quiescence.",
    # Login security S-A: passkeys are a person's global credentials (web only).
    **dict.fromkeys((
        "auth-passkey-detail", "auth-passkeys-register-options", "auth-passkeys-register-verify",
        "auth-passkeys-authenticate-options", "auth-passkeys-authenticate-verify", "auth-mfa-passkey-options",
        "auth-reauth-passkey-options", "auth-reauth-passkey",
    ), "Global passkey credential and session state is excluded from tenant quiescence."),
    # Login security S-B: remembered devices, the unusual-login code and "this wasn't me".
    **dict.fromkeys((
        "auth-devices", "auth-device-detail", "auth-login-code-resend", "auth-security-alerts-not-me",
    ), "Global sign-in risk state and account-wide revocation are excluded from tenant quiescence."),
    "control-mfa": "Global MFA credential and control-session state is excluded from tenant quiescence.",
    "auth-refresh": "Global user session state is excluded from tenant quiescence.",
    "auth-logout": "Global user session state is excluded from tenant quiescence.",
    "auth-logout-all": "Global user session state is excluded from tenant quiescence.",
    "auth-change-password": "Global credential edits are excluded from tenant quiescence.",
    "auth-forgot-password": "Global account recovery is excluded from tenant quiescence.",
    "auth-reset-password": "Global credential edits are excluded from tenant quiescence.",
    "auth-member-sign-up": "Global user creation is excluded from tenant quiescence.",
    "auth-email-verification-resend": "Global user verification is excluded from tenant quiescence.",
    "auth-email-verification-confirm": "Global user verification is excluded from tenant quiescence.",
    "auth-phone-login-start": "Global phone identity state is excluded from tenant quiescence.",
    "auth-phone-login-confirm": "Global phone identity state is excluded from tenant quiescence.",
    "auth-phone-link-start": "Global phone identity state is excluded from tenant quiescence.",
    "auth-phone-link-confirm": "Global phone identity state is excluded from tenant quiescence.",
    "auth-phone-unlink": "Global phone identity state is excluded from tenant quiescence.",
    "social-nonce": "Global social identity state is excluded from tenant quiescence.",
    "social-google": "Global social identity state is excluded from tenant quiescence.",
    "social-apple": "Global social identity state is excluded from tenant quiescence.",
    "social-oidc": "Global social identity state is excluded from tenant quiescence.",
    "social-oidc-browser-start": "Global social identity state is excluded from tenant quiescence.",
    "social-oidc-browser-callback": "Global social identity state is excluded from tenant quiescence.",
    "social-github-browser-start": "Global social identity state is excluded from tenant quiescence.",
    "social-github-browser-callback": "Global social identity state is excluded from tenant quiescence.",
    "social-github-link-start": "Global social identity state is excluded from tenant quiescence.",
    "social-oidc-link-start": "Global social identity state is excluded from tenant quiescence.",
    "social-link-callback": "Global social identity state is excluded from tenant quiescence.",
    "device-attestation-challenge": "Global device authority is excluded from tenant quiescence.",
    "device-login": "Global device authority is excluded from tenant quiescence.",
    "device-refresh": "Global device authority is excluded from tenant quiescence.",
    "device-logout": "Global device authority is excluded from tenant quiescence.",
}


HTTP_ANONYMOUS_EXEMPTIONS = {
    "apps.operations.cloud_jobs.tick_views.FreeTickView.post": "Free-only authenticated deployment coordination, with per-chunk source gates.",
    "apps.accounts.views_device.DeviceAttestationChallengeView.post": "Global device-attestation challenge state.",
    "apps.accounts.views_device.DeviceLoginView.post": "Global user and device-session state.",
    "apps.accounts.views_device.DeviceRefreshView.post": "Global device-session state.",
    "apps.accounts.views_oidc_browser.OidcBrowserStartView.post": "Global OIDC login-attempt state.",
    "apps.accounts.views_oidc_browser.OidcBrowserCallbackView.post": "Global OIDC identity state.",
    "apps.accounts.views_github.GithubBrowserStartView.post": "Global GitHub login-attempt state.",
    "apps.accounts.views_github.GithubBrowserCallbackView.post": "Global GitHub identity state.",
    "apps.accounts.views_password.ForgotPasswordView.post": "Global account-recovery state.",
    "apps.accounts.views_password.ResetPasswordConfirmView.post": "Global credential state.",
    "apps.accounts.views_phone.PhoneLoginStartView.post": "Global phone-login challenge state.",
    "apps.accounts.views_phone.PhoneLoginConfirmView.post": "Global phone identity and session state.",
    "apps.accounts.views_registration.MemberSignUpView.post": "Global user registration state.",
    "apps.accounts.views_login.LoginView.post": "Global user session state.",
    "apps.accounts.views_profile.LogoutView.post": "Global user session state.",
    "apps.accounts.views_mfa.MFAEnrollmentView.post": "Global MFA enrollment challenge state.",
    # Login security S-A: anonymous passkey ceremonies touch only global challenge and session state.
    **{f"apps.accounts.passkeys.views.{view}.post": "Global passkey challenge and session state."
       for view in ("PasskeyAuthenticateOptionsView", "PasskeyAuthenticateVerifyView", "PasskeyMfaOptionsView")},
    "apps.accounts.views_social_login.SocialNonceView.post": "Global social-login nonce state.",
    "apps.accounts.views_social_login.SocialLoginView.post": "Global social identity and session state.",
    # Login security S-A (passkeys, web only) and S-B (risk code resend, "this wasn't me").
    "apps.accounts.passkeys.views.PasskeyAuthenticateOptionsView.post": "Global passkey ceremony state.",
    "apps.accounts.passkeys.views.PasskeyAuthenticateVerifyView.post": "Global passkey credential and session state.",
    "apps.accounts.passkeys.views.PasskeyMfaOptionsView.post": "Global passkey ceremony and MFA challenge state.",
    "apps.accounts.views_login_codes.LoginCodeResendView.post": "Global sign-in challenge state.",
    "apps.accounts.views_security_alerts.SecurityAlertNotMeView.post": (
        "Global account-wide revocation; no tenant row or authority."
    ),
    "apps.payments_rail.views_connect.StripeConnectWebhookView.post": "Platform Connect routing state.",
    **{
        f"apps.hosting_requests.views_public.{view}.post": (
            "Global platform hosting-request state; no tenant row or authority."
        )
        for view in (
            "HostingRequestSubmitView", "HostingRequestOpenView", "HostingRequestResubmitView",
            "HostingInvitationResolveView", "HostingInvitationSubmitView",
        )
    },
}


HTTP_ANONYMOUS_PARTICIPANTS = {
    "apps.integrations.views_bounce.ProviderBounceWebhookView.post": "Signed opaque tenant receipt commits in tenant_write.",
    "apps.integrations.notification_wa_meta_views.MetaWebhookView.post": (
        "Raw Meta HMAC and URL generation bind one tenant; batch application, "
        "proofs, consent revocation and delivery updates commit under tenant_write."
    ),
    **WA_TWILIO_PARTICIPANTS,
    "apps.integrations.views.TelegramWebhookView.post": (
        "Verified secret and single-use private proof resolve one configuration; endpoint "
        "and audit writes take tenant_write in notification_proofs.verified_callback."
    ),
    "apps.integrations.views_messaging_webhooks.TwilioMessagingWebhookView.post": "Signed ingress stores a durable event; status uses tenant_write and STOP uses sender-scoped protection.",
    "apps.integrations.views_messaging_webhooks.MetaMessagingWebhookView.post": "Sender lock precedes event/correlation row locks; tenant status writes use tenant_write independently of module state.",
    "apps.integrations.views_bounce.BounceWebhookView.post": (
        "Verified tenant HMAC resolves one makerspace; suppression and audit commit under tenant_write."
    ),
    "apps.notifications.views_preferences.OneClickUnsubscribeView.post": (
        "Signed token resolves one tenant; save_preference holds tenant_write through its audited commit."
    ),
    # L16: a technician's own chat opt-in. The hashed token resolves one contact, locked, and the
    # write asserts its makerspace's tenant gate before consent is saved.
    "apps.maintenance.repairs.views_public.TechnicianOptInView.post": (
        "Signed token resolves one tenant's contact; accept asserts tenant writes before saving consent."
    ),
    **REPLAY_HTTP_PARTICIPANTS,
    "apps.hardware_requests.cron_views.ReturnReminderCronView.post": (
        "The fan-out reminder service takes the skip-and-count gate once per request."
    ),
    # Token-authenticated device enrollment: each view resolves the enrollment's
    # makerspace, takes the late gate for it, and the locked service re-asserts it.
    "apps.devices.views_enrollment.DeviceEnrollmentChallengeView.post": (
        "Resolves the enrollment's makerspace and asserts its source gate before mutating."
    ),
    "apps.devices.views_enrollment.DeviceEnrollmentCompleteView.post": (
        "Resolves the enrollment's makerspace and asserts its source gate before mutating."
    ),
}


ADMIN_ACTION_EXEMPTIONS = {
    "makerspaces.Makerspace.approve_archive_requests": (
        "Approving a pending lifecycle request performs the excluded tenant archive."
    ),
    "makerspaces.Makerspace.decline_archive_requests": (
        "Declining a governance request grants no authority on the frozen tenant."
    ),

    "makerspaces.MakerspaceArchiveRequest.approve_selected": (
        "Approving the request performs the excluded tenant archive."
    ),
    "makerspaces.Makerspace.archive_makerspaces": (
        "Tenant archive is expressly excluded from source quiescence."
    ),
    "makerspaces.Makerspace.purge_makerspaces": (
        "Tenant purge is expressly excluded from source quiescence."
    ),
}

from .gate_policy_p2_p_chat import HTTP_ANONYMOUS_PARTICIPANTS as chat_participants
HTTP_ANONYMOUS_PARTICIPANTS.update(chat_participants)
from . import gate_policy_r2_superadmin as _superadmin  # noqa: E402  (#185, #187A)
HTTP_EXEMPTIONS.update(_superadmin.HTTP_EXEMPTIONS)
HTTP_ANONYMOUS_PARTICIPANTS.update(_superadmin.HTTP_ANONYMOUS_PARTICIPANTS)
ADMIN_ACTION_EXEMPTIONS.update(_superadmin.ADMIN_ACTION_EXEMPTIONS)
