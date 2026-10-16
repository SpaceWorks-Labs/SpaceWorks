from django import forms
from django.contrib import admin
from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from django.db import transaction
from unfold.admin import ModelAdmin

from apps.accounts import rbac
from apps.accounts.reauthentication import require_recent_reauth
from apps.audit import services as audit
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.governance import GOVERNANCE_ACTIONS
from apps.organizations.services_governance import assert_governor_remains
from apps.organizations.admin_errors import control_mutation
from config.admin_access import SuperuserOnlyModelAdmin


class OrganizationMembershipForm(forms.ModelForm):
    class Meta:
        model = OrganizationMembership
        fields = "__all__"

    def clean_granted_actions(self):
        """Reject actions rbac would silently drop.

        `rbac._org_actions_for` filters unknown and forbidden values out before
        granting anything, so an unvalidated typo here would save cleanly and then
        confer nothing -- the operator has no way to tell a granted action from an
        ignored one. Reject malformed lists, forbidden grants and unknown actions.
        """
        actions = self.cleaned_data.get("granted_actions")
        if not isinstance(actions, list) or any(
            not isinstance(item, str) for item in actions
        ):
            raise forms.ValidationError("Use a list of action values.")
        values = set(actions)
        if values & rbac.ROLE_FORBIDDEN_ACTIONS:
            raise forms.ValidationError(
                "This action cannot be granted through an organization."
            )
        unknown = values - rbac.ALL_ACTIONS
        if unknown:
            raise forms.ValidationError(f"Unknown action value: {sorted(unknown)[0]}.")
        if rbac.Action.MANAGE_MACHINES in values:
            # machines.role_scope.manage_scope_for() derives machine reach from a local
            # MakerspaceMembership role and resolves an organization-only actor to
            # NOTHING, so this action would read as effective in rbac while every
            # machine list and mutation stayed empty or denied. Refuse it rather than
            # grant something inert; machine scope for organization grants has to be
            # defined before it can be offered.
            raise forms.ValidationError(
                "manage_machines cannot be granted through an organization yet: "
                "machine scope is derived from a makerspace membership."
            )
        return sorted(values)

    def clean_governance_actions(self):
        actions = self.cleaned_data.get("governance_actions")
        if actions in (None, ""):
            return []
        if not isinstance(actions, list) or any(
            not isinstance(item, str) for item in actions
        ):
            raise forms.ValidationError("Use a list of governance action values.")
        unknown = set(actions) - GOVERNANCE_ACTIONS
        if unknown:
            raise forms.ValidationError(
                f"Unknown governance action: {sorted(unknown)[0]}."
            )
        return sorted(set(actions))


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(RecentReauthenticationAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    form = OrganizationMembershipForm
    list_display = (
        "organization",
        "user",
        "status",
        "created_by",
        "updated_at",
    )
    list_filter = ("status", "organization")
    search_fields = (
        "organization__name",
        "organization__slug",
        "user__username",
        "user__email",
    )
    autocomplete_fields = ("organization", "user")
    readonly_fields = ("created_by", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("organization", "user") if obj else ())

    @transaction.atomic
    @control_mutation
    def save_model(self, request, obj, form, change):
        require_recent_reauth(request)
        organization = Organization.objects.select_for_update().get(pk=obj.organization_id)
        if change:
            assert_governor_remains(organization, replaced_id=obj.pk,
                                   status=obj.status, actions=obj.governance_actions)
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        audit.record(
            request.user,
            (
                "organization.membership_updated"
                if change
                else "organization.membership_created"
            ),
            target=obj,
            meta={
                "organization_slug": obj.organization.slug,
                "user_id": obj.user_id,
                "status": obj.status,
            },
        )

    # Deleting a membership revokes authority across every makerspace the organization
    # reaches, so it is a state-changing control-plane operation and must be audited.
    # Overriding save_model alone would leave both admin delete paths silent.
    @transaction.atomic
    @control_mutation
    def delete_model(self, request, obj):
        require_recent_reauth(request)
        organization = Organization.objects.select_for_update().get(pk=obj.organization_id)
        assert_governor_remains(organization, replaced_id=obj.pk, deleting=True)
        self._record_deletion(request, obj)
        super().delete_model(request, obj)

    @transaction.atomic
    @control_mutation
    def delete_queryset(self, request, queryset):
        require_recent_reauth(request)
        for obj in queryset.order_by("organization_id", "pk"):
            self.delete_model(request, obj)

    def _record_deletion(self, request, obj):
        audit.record(
            request.user,
            "organization.membership_deleted",
            target=obj,
            meta={
                "organization_slug": obj.organization.slug,
                "user_id": obj.user_id,
                "granted_actions": sorted(obj.granted_actions or []),
            },
        )

