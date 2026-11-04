"""Owner selection used only when adding a makerspace in /control/."""

from django import forms
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from rest_framework.exceptions import APIException

from apps.makerspaces.admin_capabilities import MakerspaceAdminForm
from apps.organizations.models import Organization
from apps.tenant_migration.gate_errors import SourceMigrationGateError


class MakerspaceAddForm(MakerspaceAdminForm):
    owner_organization = forms.ModelChoiceField(
        queryset=Organization.objects.filter(is_active=True).order_by("name", "id"),
        required=False,
        help_text="Choose an active organization, or enter a new organization name below.",
    )
    new_organization_name = forms.CharField(
        max_length=200, required=False,
        help_text="Creates a new owner organization instead of selecting an existing one.",
    )
    # Set only by a hosting request's pre-filled link; rendered (hidden) on managed
    # deployments and ignored everywhere else.
    hosting_request = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)

    def clean(self):
        cleaned = super().clean()
        if bool(cleaned.get("owner_organization")) == bool(cleaned.get("new_organization_name")):
            message = "Choose an existing organization or enter a new name, exactly one."
            self.add_error("owner_organization", message)
            self.add_error("new_organization_name", message)
        return cleaned


def _detail(exc):
    if isinstance(exc, Http404):
        return "the makerspace is not visible to superadmins."
    detail = getattr(exc, "detail", None) or str(exc)
    if isinstance(detail, dict):
        detail = detail.get("detail") or " ".join(str(value) for value in detail.values())
    if isinstance(detail, list):
        detail = " ".join(str(value) for value in detail)
    return str(detail)


class MakerspaceOwnerAdminMixin:
    """Add-only owner fields and atomic owner assignment for ``MakerspaceAdmin``."""

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = MakerspaceAddForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None:
            from apps.hosting_requests.availability import admin_available

            fields = ("owner_organization", "new_organization_name")
            if admin_available():
                fields += ("hosting_request",)
            return (("Owner organization", {"fields": fields}), *fieldsets)
        return fieldsets

    def assign_owner(self, request, obj, form):
        from apps.organizations.services_owner import assign_owner_organization

        organization = form.cleaned_data.get("owner_organization")
        assign_owner_organization(
            request.user, obj.pk,
            organization_id=organization.pk if organization is not None else None,
            new_name=form.cleaned_data.get("new_organization_name") or None,
        )
        from apps.hosting_requests.availability import admin_available

        hosting_request = form.cleaned_data.get("hosting_request")
        if hosting_request and admin_available():
            from apps.hosting_requests.workflow import link_created_makerspace

            link_created_makerspace(request.user, hosting_request, obj)

    def add_view(self, request, form_url="", extra_context=None):
        try:
            return super().add_view(request, form_url, extra_context)
        except (APIException, Http404, SourceMigrationGateError) as exc:
            # changeform_view runs inside transaction.atomic, so the makerspace, the
            # organization, the owner link and their audit rows have all rolled back.
            # A concurrent deactivation or gate change must not surface as a 500.
            self.message_user(request, f"Makerspace was not created: {_detail(exc)}", messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())
