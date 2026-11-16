"""No reference authorizes sending or associates an account by its phone."""
from .models_cutover import NotificationProviderReference


def remember(delivery):
    if delivery.channel not in {"sms", "whatsapp"} or not delivery.provider_id or not delivery.sender_key:
        return
    row, _ = NotificationProviderReference.objects.get_or_create(provider=delivery.provider,
        sender_key=delivery.sender_key, provider_id=delivery.provider_id, defaults={
            "phone_hash": delivery.recipient_phone_hash, "delivery_reference": delivery.pk,
            "makerspace_reference": delivery.makerspace_id, "generation": delivery.integration_generation,
            "attempt": delivery.attempt_count})
    if (row.delivery_reference != delivery.pk or row.makerspace_reference != delivery.makerspace_id
            or row.generation != delivery.integration_generation or row.attempt != delivery.attempt_count
            or (row.phone_hash and delivery.recipient_phone_hash and row.phone_hash != delivery.recipient_phone_hash)):
        row.ambiguous = True
        row.save(update_fields=["ambiguous"])
    elif not row.phone_hash and delivery.recipient_phone_hash:
        row.phone_hash = delivery.recipient_phone_hash
        row.save(update_fields=["phone_hash"])


def retired_target_known(receipt, event):
    """An exact permanent reference can settle facts for a deleted target only."""
    from .models_contract import NotificationDelivery
    rows = NotificationProviderReference.objects.filter(provider=receipt.provider,
        sender_key=receipt.sender_key, provider_id=event.provider_id, ambiguous=False,
        makerspace_reference=receipt.makerspace_reference, generation=receipt.generation)
    if event.delivery_id is not None:
        rows = rows.filter(delivery_reference=event.delivery_id)
    if event.delivery_attempt is not None:
        rows = rows.filter(attempt=event.delivery_attempt)
    reference = rows.first()
    return bool(receipt.protection_applied and reference and reference.delivery_reference
        and not NotificationDelivery.objects.filter(pk=reference.delivery_reference).exists())
