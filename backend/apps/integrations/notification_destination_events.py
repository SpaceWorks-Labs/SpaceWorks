"""Destination-wide provider facts; account unlink remains account-local."""

from django.db import transaction
from django.utils import timezone

from apps.accounts import rbac
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, NotificationEndpoint


def live_destination(configuration, identity_digest):
    return rbac.scope_notification_policy(NotificationEndpoint.objects.all(),
        makerspace_id=configuration.makerspace_id).filter(
        configuration=configuration, identity_digest=identity_digest,
        integration_generation=configuration.generation,
        integration_identity=configuration.integration_identity,
        verification_state="verified", revoked_at=None)


def apply_destination_event(configuration, event, *, identity_digest=""):
    if not (event.opt_out or event.inbound or event.opt_in):
        return
    with tenant_write(configuration.makerspace_id), transaction.atomic():
        current = ChannelConfiguration.objects.select_for_update().get(pk=configuration.pk)
        if (current.generation != configuration.generation
                or current.integration_identity != configuration.integration_identity):
            return
        identity_digest = identity_digest or event.identity_digest
        if not identity_digest and event.endpoint_id:
            identities = NotificationEndpoint.objects.filter(
                pk=event.endpoint_id, configuration=current,
                integration_generation=current.generation,
            ).values_list("identity_digest", flat=True)
            identity_digest = next(iter(identities), "")
        if not identity_digest:
            return
        endpoints = list(live_destination(current, identity_digest).select_for_update().order_by("pk"))
        from .notification_proofs import revoke
        if event.opt_out:
            for endpoint in endpoints:
                revoke(endpoint, actor=endpoint.user)
        elif endpoints:
            values = {}
            if event.inbound:
                values["last_inbound_at"] = timezone.now()
            if event.opt_in:
                values["consented_at"] = timezone.now()
            NotificationEndpoint.objects.filter(pk__in=[row.pk for row in endpoints]).update(**values)
        return bool(endpoints)
