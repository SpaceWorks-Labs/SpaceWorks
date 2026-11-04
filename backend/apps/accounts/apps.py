from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        from apps.accounts import checks  # noqa: F401 -- register URL drift guard
        # D2 owns the single transition hook registry. D4 registers claim-code
        # revocation into it; D5 will extend this same hook with live-session cleanup.
        from apps.accounts.services_claim import register_transition_revocation
        from django.contrib.auth.signals import user_logged_in
        from apps.accounts.control_mfa import stamp_password_session

        from apps.accounts.saved_details.fields import install_core_profile_fields
        install_core_profile_fields()
        register_transition_revocation()
        # A lost staff role revokes that makerspace's native staff grants (U-A2).
        from apps.accounts.services_staff_grants import connect_signals
        connect_signals()
        # A staff role gained without a second factor starts the 3-day grace (#128 C-1).
        from apps.accounts.mfa_grace import connect_signals as connect_grace_signals
        connect_grace_signals()
        # U-B: the "you were granted a staff role" personal notice.
        from apps.accounts.staff_role_notices import register as register_staff_role_notices
        register_staff_role_notices()
        from apps.accounts.passkeys import checks as passkey_checks  # noqa: F401 -- RP ID system check
        # Failed sign-ins feed the automatic IP block; rule edits drop the rule cache (S-C).
        from apps.accounts.ip_guard_signals import connect_signals as connect_ip_guard_signals
        connect_ip_guard_signals()
        # S-B: unusual-login failure counts and the security alerts (mfa_changed, lockout).
        from apps.accounts.login_risk_signals import connect_signals as connect_login_risk_signals
        connect_login_risk_signals()
        user_logged_in.connect(stamp_password_session, dispatch_uid="accounts.control_mfa.password_session")
