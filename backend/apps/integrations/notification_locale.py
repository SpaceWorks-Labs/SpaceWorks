"""Render a delivery in the RECIPIENT's language (explicit user, makerspace default, system)."""
from contextlib import contextmanager


@contextmanager
def recipient_locale(delivery_id, makerspace_id):
    """Wrap a whole send (inbox row, push, SMS, chat, email body) in the recipient's locale.

    A one-locale deployment answers without a query: the recipient row is only loaded on demand.
    """
    from config.locale_resolution import override_for
    from .models_contract import NotificationDelivery

    def recipient():
        row = NotificationDelivery.objects.filter(pk=delivery_id).select_related("envelope__recipient").first()
        return row.envelope.recipient if row else None

    with override_for(user=recipient, makerspace=makerspace_id):
        yield
