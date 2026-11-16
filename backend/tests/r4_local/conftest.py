import pytest
from django.core.cache import cache


@pytest.fixture
def mailbox(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail
    mail.outbox.clear()
    cache.clear()
    return mail.outbox
