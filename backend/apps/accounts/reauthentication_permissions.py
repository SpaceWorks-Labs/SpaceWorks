"""Reusable DRF boundary for sensitive browser mutations."""

from apps.accounts.reauthentication import require_recent_reauth


class RecentReauthenticationMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            require_recent_reauth(request)
