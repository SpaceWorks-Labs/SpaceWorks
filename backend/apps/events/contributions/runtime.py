"""Complete contributor ports composed from canonical domain services."""
from apps.accounts.models import User
from apps.events import event_authority
from apps.events.models import Event
from apps.events.programme_locks import fences, assert_lock_context, lock_authority
from apps.makerspaces.guards import require_feature, require_module
from .audience_adapter import require_role_audience
from .requirements_adapter import require_requirements
from .grant_sources import GrantSources
from .team_access import TeamAccess
from .admission_adapter import CanonicalContributorAdmissions
from apps.events.programme.role_forms import RoleForms


class ContributorPorts:
    forms, grants, teams = RoleForms(), GrantSources(), TeamAccess()
    admissions = CanonicalContributorAdmissions()
    fences = staticmethod(fences)
    require_role_audience = staticmethod(require_role_audience)
    require_requirements = staticmethod(require_requirements)

    def prepare_private_write(self, *, makerspace_id):
        # The shared write boundary prepares and scopes tenant custody before
        # its first lock. This preflight does no opportunistic under-lock KMS.
        from apps.encryption.write_fence import assert_mapped_write_allowed
        assert_mapped_write_allowed(makerspace_id)

    def lock_authority_locked(self, *, actor_id, event_id, locks):
        assert_lock_context(locks)
        return lock_authority(User.objects.filter(pk=actor_id).first(), Event.objects.get(pk=event_id))

    def require_event_feature(self, *, event_id, feature):
        event = Event.objects.select_related("makerspace").get(pk=event_id)
        require_module(event.makerspace, "events")
        require_feature(event.makerspace, feature)

    def visible_posting_ids(self, *, actor_id, event_id):
        from django.http import Http404
        from rest_framework.exceptions import APIException
        from .models_roles import EventRolePosting
        result = []
        for pk in EventRolePosting.objects.filter(event_id=event_id, state="open").values_list("pk", flat=True):
            try:
                require_role_audience(actor_id=actor_id, event_id=event_id, posting_id=pk)
            except (Http404, APIException):
                continue
            result.append(pk)
        return tuple(result)

    def delegation_scope(self, *, actor_id, target_id, permissions, operation, row_id):
        from apps.events.contracts.services import DelegationScope
        from .authority import HELPER_PERMISSIONS, can_delegate_helpers
        event = Event.objects.get(pk=target_id)
        actor = User.objects.filter(pk=actor_id).first()
        # Shared invitations have no track/window fields. Consequently a helper
        # can issue them only when one current source covers the whole event.
        for role, allowed in HELPER_PERMISSIONS.items():
            if permissions and set(permissions) <= allowed:
                return can_delegate_helpers(actor=actor, target=event, permissions=permissions,
                    scope=DelegationScope(event_id=event.pk, helper_role=role))
        return False

    def organizer_ids(self, *, event_id):
        event = Event.objects.get(pk=event_id)
        return tuple(user.pk for user in User.objects.filter(is_active=True, access_status="active",
            is_tenant_dump_stub=False).order_by("pk") if event_authority.can_manage_grants(user, event))

    def deliver_help(self, **kwargs):
        from .runtime_notices import deliver_help
        return deliver_help(**kwargs)

    def deliver_contribution(self, **kwargs):
        from .runtime_notices import deliver_contribution
        return deliver_contribution(**kwargs)

    def enqueue_notice(self, *, kind, notice_id):
        from .runtime_notices import enqueue
        return enqueue(kind=kind, notice_id=notice_id)
