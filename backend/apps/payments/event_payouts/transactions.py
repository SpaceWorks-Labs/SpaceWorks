"""Source/fence/host/authority/obligation locks with no removable-app imports."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from apps.accounts.models import User
from apps.encryption.account_write_fence import account_fences
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole, MembershipAdditionalRole
from apps.organizations.models import Organization, OrganizationMembership, OrganizationMakerspace
from apps.tenant_migration.gate_runtime import boundary_tenant_write, assert_write_allowed
from .authority import authorize
from .errors import require
from .obligation_models import EventPayoutObligation
from .command_models import EventPayoutCommandReceipt


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        cls=DjangoJSONEncoder, allow_nan=False).encode()).hexdigest()


def lock_finance_authority(actor, space):
    fresh = User.objects.get(pk=actor.pk)
    links = OrganizationMakerspace.objects.filter(makerspace=space)
    organization_ids = list(links.values_list("organization_id", flat=True))
    list(Organization.objects.select_for_update().filter(pk__in=organization_ids).order_by("pk"))
    memberships = list(MakerspaceMembership.objects.select_for_update().filter(
        user=fresh, makerspace=space).order_by("pk"))
    additions = list(MembershipAdditionalRole.objects.select_for_update().filter(
        membership__in=memberships).order_by("pk"))
    role_ids = {row.assigned_role_id for row in memberships if row.assigned_role_id}
    role_ids.update(row.role_id for row in additions)
    list(MakerspaceRole.objects.select_for_update().filter(pk__in=role_ids).order_by("pk"))
    list(links.select_for_update().order_by("pk"))
    list(OrganizationMembership.objects.select_for_update().filter(user=fresh,
        organization_id__in=organization_ids).order_by("pk"))
    return fresh


@dataclass
class CoreContext:
    obligation: object
    actor: object
    data: dict = field(repr=False)
    digest: str
    replay: dict | None

    def cas(self):
        require(self.data["expected_version"] == self.obligation.version, "stale_version",
                current_version=self.obligation.version)

    def finish(self, **reference):
        result = {"id": str(self.obligation.pk), "version": self.obligation.version,
                  "state": self.obligation.state, **reference}
        EventPayoutCommandReceipt.objects.create(makerspace=self.obligation.makerspace,
            obligation=self.obligation, actor=self.actor, operation_id=self.data["operation_id"],
            command_digest=self.digest, response_reference=result)
        return result


@contextmanager
def command(*, request, obligation_id, data, action, payout=False, owner=False, prefix=None):
    seed = EventPayoutObligation.objects.select_related("makerspace").get(pk=obligation_id)
    authorize(request, seed.makerspace, owner_id=seed.owner_member_id, owner=owner,
              payout=payout, mutation=True)
    assert_write_allowed(seed.makerspace_id)
    key = prepare_tenant_key(seed.makerspace_id)
    accounts = tuple(sorted({request.user.pk, *([seed.owner_member_id] if seed.owner_member_id else [])}))
    digest = fingerprint({"action": action, "obligation_id": seed.pk, "body": data})
    with boundary_tenant_write(seed.makerspace_id), tenant_key_context(key), transaction.atomic(), account_fences(
        accounts, (seed.makerspace_id,),
    ):
        # Attached cancellation supplies an event/domain prefix which acquires
        # host/authority before the pool. Normal core commands lock no Event rows.
        if prefix is not None:
            space, request.user = prefix.lock_before_obligation(request=request, seed=seed)
        else:
            space = Makerspace.objects.select_for_update().get(pk=seed.makerspace_id)
            request.user = lock_finance_authority(request.user, space)
        authorize(request, space, owner_id=seed.owner_member_id, owner=owner, payout=payout, mutation=True)
        row = EventPayoutObligation.objects.select_for_update().get(pk=seed.pk)
        require(row.makerspace_id == seed.makerspace_id and row.owner_member_id == seed.owner_member_id, "scope_changed")
        row.makerspace = space
        receipt = EventPayoutCommandReceipt.objects.filter(operation_id=data["operation_id"]).first()
        if receipt:
            require(receipt.actor_id == request.user.pk and receipt.obligation_id == row.pk
                    and receipt.command_digest == digest, "idempotency_conflict")
        yield CoreContext(row, request.user, data, digest, receipt.response_reference if receipt else None)
