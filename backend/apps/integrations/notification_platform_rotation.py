"""Platform rotation fences every explicitly opted-in tenant and retains old verifiers."""
from .models_endpoints import ChannelConfiguration
from .notification_sender import preserve_configuration


def lock_tenants(channel):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    tenant_ids = ChannelConfiguration.objects.filter(channel=channel, use_platform_sender=True,
        credentials="").order_by("makerspace_id").values_list("makerspace_id", flat=True).distinct()
    tenant_ids = set(tenant_ids)
    for tenant_id in sorted(tenant_ids):
        assert_write_allowed(tenant_id)
    return tenant_ids


def prepare(channel, platform, locked_tenants):
    configs = ChannelConfiguration.objects.select_for_update().filter(channel=channel,
        use_platform_sender=True, credentials="")
    if set(configs.values_list("makerspace_id", flat=True)) - locked_tenants:
        from .notification_cutover import CutoverClosed
        # A new tenant opted in before the settings lock. Restart rather than
        # acquiring an earlier tenant lock while holding the later settings lock.
        raise CutoverClosed()
    for config in configs:
        preserve_configuration(config, retired=True)
        config.generation += 1
        config.credential_version = config.generation
        config.activation_hold = True
        config.sender_key = (f"twilio:{platform.account_sid}:{platform.notifications_from_number}" if channel == "sms"
            else f"meta:{platform.business_account_id}:{platform.phone_number_id}")
        config.integration_identity = config.sender_key if channel == "sms" else platform.phone_number_id
        config.save()
        config.templates.update(approved=False, needs_review=True)


def finish(channel):
    for config in ChannelConfiguration.objects.filter(channel=channel, use_platform_sender=True, credentials=""):
        preserve_configuration(config)
