"""Django authentication backend with permanent Lane D stub refusal."""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
from apps.accounts.staff_identity import platform_q


class SpaceWorksModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Django admin does not use the API's context-aware serializer. Keep its
        # password door restricted before a Django session can be created.
        if request is not None and request.path.rstrip("/") == "/control/login":
            User = get_user_model()
            value = str(username or "").strip()
            candidates = User.objects.filter(
                Q(username=value) | Q(email__iexact=value), platform_q(),
                retired_at__isnull=True, is_active=True,
            ).distinct()
            user = candidates.first() if value and candidates.count() == 1 else None
            if user is None:
                User().set_password(password)
                return None
            return user if user.check_password(password) and self.user_can_authenticate(user) else None
        return super().authenticate(request, username=username, password=password, **kwargs)

    def user_can_authenticate(self, user):
        return bool(
            not getattr(user, "is_tenant_dump_stub", False)
            and getattr(user, "retired_at", None) is None
            # Decision 361: a restricted or suspended PERSON may sign in; the session it gets
            # reaches only their own charges and sign-out (`restricted_admission`).
            and _state_may_sign_in(user)
            and super().user_can_authenticate(user)
        )


def _state_may_sign_in(user):
    from apps.accounts.restricted_admission import state_may_sign_in
    return state_may_sign_in(user)
