"""Exercise personal outbox and real email delivery without a Celery broker."""


def run_outbox(monkeypatch, settings):
    from apps.integrations.dispatch_delivery import _deliver
    from apps.integrations.models import EmailLog
    from apps.integrations.notification_tasks import deliver_envelope

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", deliver_envelope.run)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue",
                        lambda pk: _deliver(EmailLog.objects.get(pk=pk)))

