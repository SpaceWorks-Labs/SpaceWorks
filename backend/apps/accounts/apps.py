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

        register_transition_revocation()
        user_logged_in.connect(stamp_password_session, dispatch_uid="accounts.control_mfa.password_session")
