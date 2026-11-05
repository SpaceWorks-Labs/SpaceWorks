from django.contrib.auth import logout
from django.db import models
from django.http import HttpResponseForbidden
from django.urls import reverse

from config.admin_confirm import ConfirmDangerousActionsMixin
from config.admin_source_gate import AdminSourceGateMixin
from config.admin_scope_registry import (  # noqa: F401
    GLOBAL_ADMIN_MODELS,
    NESTED_MAKERSPACE_LOOKUPS,
)


class AdminSuperuserOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        try:
            prefix = reverse("admin:index")
        except Exception:
            prefix = "/control/"
        self.admin_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
        self.admin_root = self.admin_prefix.rstrip("/")
        try:
            self.admin_login_path = reverse("admin:login")
        except Exception:
            self.admin_login_path = f"{self.admin_prefix}login/"

    def __call__(self, request):
        if self._is_admin_path(request.path):
            user = getattr(request, "user", None)
            if getattr(user, "is_authenticated", False) and self._has_access(user):
                from apps.accounts.control_mfa import session_verified
                if not session_verified(request) and request.path != f"{self.admin_prefix}logout/":
                    from django.shortcuts import redirect
                    return redirect("/mfa/control/")
            user = getattr(request, "user", None)
            if getattr(user, "is_authenticated", False) and not self._has_access(user):
                # The admin login view authenticates before we can see the user, so an
                # is_staff non-superuser can mint a Django admin session. Flush it here so
                # the stray session can't linger (and the user isn't locked out of logout).
                # The React staff console uses JWT, not this session, so this is safe.
                logout(request)
                return HttpResponseForbidden()
        return self.get_response(request)

    def process_view(self, request, callback, callback_args, callback_kwargs):
        if request.method != "POST" or not self._is_admin_path(request.path):
            return None
        from apps.accounts.reauthentication_control import sensitive_control_request, RecentReauthenticationAdminMixin
        if sensitive_control_request(request, callback):
            return RecentReauthenticationAdminMixin()._recent_redirect(request)
        return None

    def _is_admin_path(self, path):
        return path == self.admin_root or path.startswith(self.admin_prefix)

    def _password_login_blocked(self, request):
        """Member method switches never remove the platform password door.

        In particular, PLATFORM_ADMIN_SSO=False keeps its password fallback;
        configuring SSO does not turn a member setting into platform policy.
        """
        return False

    def _has_access(self, user):
        from apps.accounts.models import User
        from apps.accounts.staff_identity import is_platform

        return bool(
            user.is_active
            and is_platform(user)
            and user.retired_at is None
            and user.is_superuser
            and getattr(user, "access_status", None) == User.AccessStatus.ACTIVE
            # The generated first-run credential must rotate before reaching the admin too,
            # otherwise it could bypass the API/staff-console forced-change gate.
            and not getattr(user, "must_change_password", False)
        )


class SuperuserOnlyModelAdmin(ConfirmDangerousActionsMixin, AdminSourceGateMixin):
    def resolve_hidden_lookup(self):
        """The makerspace-id lookup for this model, or None for a global model.

        The source gate uses it to refuse writes into a tenant that is migrating.
        """
        from apps.makerspaces.models import Makerspace

        model = self.model
        model_key = f"{model._meta.app_label}.{model._meta.model_name}"
        if model_key in GLOBAL_ADMIN_MODELS:
            return None
        if model is Makerspace:
            return "id"

        for field in model._meta.get_fields():
            if (
                field.name == "makerspace"
                and isinstance(field, (models.ForeignKey, models.OneToOneField))
            ):
                return "makerspace_id"

        return NESTED_MAKERSPACE_LOOKUPS.get(model_key)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if self.model._meta.label_lower == "accounts.user":
            from config.admin_account_scope import scope_account_rows

            queryset = scope_account_rows(queryset)
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # A plain (non-autocomplete) FK ModelChoiceField builds its options from the
        # target model's default manager, NOT the target admin's get_queryset, so a
        # User FK widget is scoped here the same way the account changelist is.
        from apps.accounts.models import User

        if getattr(getattr(db_field, "remote_field", None), "model", None) is User:
            from config.admin_account_scope import scope_account_rows

            kwargs["queryset"] = scope_account_rows(kwargs.get("queryset", User.objects.all()))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def _obj_in_hidden(self, obj):
        """True for a retired staff account or one whose makerspace cannot serve.

        Complements get_queryset by blocking the object-level view/change/delete
        pages too, so /control/ cannot reach such an account by id."""
        if obj is None or self.model._meta.label_lower != "accounts.user":
            return False
        from config.admin_account_scope import staff_account_hidden

        return staff_account_hidden(obj)

    def _has_superuser_access(self, request):
        from apps.accounts.models import User
        from apps.accounts.staff_identity import is_platform

        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and is_platform(user)
            and user.retired_at is None
            and user.is_superuser
            and getattr(user, "access_status", None) == User.AccessStatus.ACTIVE
            and not getattr(user, "must_change_password", False)
        )

    def has_view_permission(self, request, obj=None):
        return self._has_superuser_access(request) and not self._obj_in_hidden(obj)

    def has_add_permission(self, request):
        return self._has_superuser_access(request)

    def has_change_permission(self, request, obj=None):
        return self._has_superuser_access(request) and not self._obj_in_hidden(obj)

    def has_delete_permission(self, request, obj=None):
        return self._has_superuser_access(request) and not self._obj_in_hidden(obj)

    def has_module_permission(self, request):
        return self._has_superuser_access(request)


# Preserve the middleware's dotted path while keeping this registry/admin module under
# the repository's hard file-size ceiling.
from config.admin_access_csp import AdminCspEvalMiddleware  # noqa: E402,F401
