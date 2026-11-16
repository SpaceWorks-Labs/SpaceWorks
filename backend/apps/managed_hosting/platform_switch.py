"""Per-space choice: may the PLATFORM's credentials serve this space when it has none (decisions 240, 281)?

One answer for five integrations, read by every fallback resolver:

* ``email``, ``sms``, ``whatsapp``, ``native_push`` -> ``ChannelConfiguration.use_platform_sender``
  of that channel's row (the Space Manager's channel settings).
* ``wallet`` -> ``MakerspaceWalletCredentials.use_platform_credentials``.

A space with no row has made no choice, which is ON (the default for new spaces). OFF means no
platform fallback for that space: the channel is simply unavailable and the in-app inbox still
delivers. A space's OWN credentials are never affected by this switch.
"""
CHANNELS = ("email", "sms", "whatsapp", "native_push", "wallet")


def platform_allowed(makerspace, channel) -> bool:
    """True unless the Space Manager switched the platform fallback off for ``channel``."""
    if makerspace is None or channel not in CHANNELS:
        return True
    pk = getattr(makerspace, "pk", makerspace)
    if channel == "wallet":
        from apps.card_designs.models import MakerspaceWalletCredentials
        row = MakerspaceWalletCredentials.objects.filter(makerspace_id=pk).values_list(
            "use_platform_credentials", flat=True).first()
    else:
        from apps.integrations.models import ChannelConfiguration
        row = ChannelConfiguration.objects.filter(makerspace_id=pk, channel=channel).values_list(
            "use_platform_sender", flat=True).first()
    return True if row is None else bool(row)


def platform_switches(makerspace) -> dict:
    """All five switches for the settings screens."""
    return {channel: platform_allowed(makerspace, channel) for channel in CHANNELS}
