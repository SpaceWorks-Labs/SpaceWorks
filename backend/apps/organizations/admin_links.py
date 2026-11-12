"""Owner-link administration uses the same root locks and gates as the console."""

from django import forms
from django.contrib import admin
from django.db import transaction
from rest_framework.exceptions import APIException
from unfold.admin import ModelAdmin

from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import assert_write_allowed
from config.admin_access import SuperuserOnlyModelAdmin
from .models import Organization, OrganizationMakerspace
from .services_console import change_link
from django.utils.translation import gettext


class OrganizationLinkForm(forms.ModelForm):
    class Meta:
        model = OrganizationMakerspace
        fields = "__all__"

    def clean(self):
        data = super().clean()
        organization = data.get("organization") or getattr(self.instance, "organization", None)
        if organization and not organization.is_active:
            raise forms.ValidationError(gettext("Reactivate the organization before linking a makerspace."))
        return data


@admin.register(OrganizationMakerspace)
class OrganizationMakerspaceAdmin(RecentReauthenticationAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    form = OrganizationLinkForm
    list_display = ("organization", "makerspace", "relationship", "created_by", "created_at")
    list_filter = ("relationship", "makerspace")
    search_fields = ("organization__name", "organization__slug", "makerspace__name")
    autocomplete_fields = ("organization", "makerspace")
    readonly_fields = ("created_by", "created_at", "updated_at")

    def get_form(self, request, obj=None, **kwargs):
        base = super().get_form(request, obj, **kwargs)
        refusal = getattr(request, "_organization_link_refusal", None)
        if refusal is None:
            return base

        class RefusedLinkForm(base):
            def clean(self):
                super().clean()
                raise forms.ValidationError(refusal)

        return RefusedLinkForm

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except APIException as exc:
            if request.method != "POST":
                raise
            # Django's POST transaction has rolled back before rendering the bound form.
            # A request-local error avoids another save and never leaks to other admins.
            detail = exc.detail.get("detail", exc.detail) if isinstance(exc.detail, dict) else exc.detail
            request._organization_link_refusal = str(detail)
            try:
                return super().changeform_view(request, object_id, form_url, extra_context)
            finally:
                del request._organization_link_refusal

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, "organization", "makerspace") if obj else fields

    def save_model(self, request, obj, form, change):
        row = change_link(request.user, obj.organization_id, obj.makerspace_id, relationship=obj.relationship)
        obj.__dict__.update(row.__dict__)

    def delete_model(self, request, obj):
        change_link(request.user, obj.organization_id, obj.makerspace_id)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        links = list(queryset.order_by("makerspace_id", "organization_id"))
        makerspace_ids = sorted({row.makerspace_id for row in links})
        # Capture release takes the gate before writing makerspace-scoped audit rows.
        # Match that order for every tenant before taking any root row lock.
        for makerspace_id in makerspace_ids:
            assert_write_allowed(makerspace_id)
        # Acquire every root first: do not discover a lower-PK root after an org lock.
        list(Makerspace.objects.select_for_update().filter(
            pk__in=makerspace_ids,
        ).order_by("pk"))
        # Fence the complete organization set before any per-link service call.
        list(Organization.objects.select_for_update().filter(
            pk__in=[row.organization_id for row in links],
        ).order_by("pk"))
        for row in links:
            change_link(request.user, row.organization_id, row.makerspace_id)
