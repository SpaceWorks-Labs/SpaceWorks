"""Browser OAuth proofs require the actor and challenge from the authenticated URL."""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, NotificationEndpointChallenge
from .notification_proofs import verified_callback
from .notification_slack_oauth import read_state

OAUTH_CHANNELS = frozenset({"slack", "mattermost", "discord"})


def verify_oauth(challenge, request):
    # Serialize completion before token exchange, so concurrent requests cannot
    # exchange one state twice. The provider HTTP clients have bounded timeouts.
    failure = None
    endpoint = None
    with tenant_write(challenge.makerspace_id), transaction.atomic():
        config = ChannelConfiguration.objects.select_for_update().get(pk=challenge.configuration_id)
        locked = NotificationEndpointChallenge.objects.select_for_update().get(
            pk=challenge.pk, user=request.user, configuration=config,
        )
        state = request.data.get("state")
        if not state or not request.data.get("code"):
            raise ValidationError({"proof": "OAuth code and state are required."})
        read_state(config, state, user_id=request.user.pk, challenge_id=locked.pk)
        try:
            endpoint = verified_callback(config, request, expected_user_id=request.user.pk,
                                         expected_challenge_id=locked.pk)
        except ValidationError as exc:
            # consume() commits failed proof attempts before it raises. Preserve
            # that budget even though this outer lock serializes token exchanges.
            failure = exc
    if failure is not None:
        raise failure
    return endpoint
