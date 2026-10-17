"""Signed, attempt-bound client correlation echoed by Meta status webhooks."""
from django.core import signing

SALT = "notification.meta.delivery.v1"


def client_reference(configuration, delivery):
    # Contains identifiers only; no destination, private content or credentials.
    return signing.dumps([configuration.pk, configuration.generation,
                          delivery.pk, delivery.attempt_count], salt=SALT)


def referenced_delivery(configuration, value):
    if not isinstance(value, str) or len(value) > 512:
        return None, None
    try:
        config_id, generation, delivery_id, attempt = signing.loads(value, salt=SALT)
    except (signing.BadSignature, ValueError, TypeError):
        return None, None
    if (config_id != configuration.pk or generation != configuration.generation
            or type(delivery_id) is not int or type(attempt) is not int):
        return None, None
    return delivery_id, attempt
