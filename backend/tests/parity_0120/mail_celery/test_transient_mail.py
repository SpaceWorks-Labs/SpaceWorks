"""Secret-bearing mail and SMS leave the request: sealed, queued after commit, delivered by the worker, never doubled."""
from unittest.mock import patch

import pytest

from apps.integrations import transient_mail
from apps.integrations.dispatch import dispatch_email
from apps.integrations.models import EmailLog
from apps.integrations.tasks_transient import deliver_transient_email_task

pytestmark = pytest.mark.django_db
CODE = "482913"


@pytest.fixture(autouse=True)
def _worker_mode(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = False


def _send(django_capture_on_commit_callbacks, **kwargs):
    with patch("apps.integrations.tasks_transient.deliver_transient_email_task.delay") as delay, \
            patch("apps.integrations.dispatch._deliver") as deliver:
        with django_capture_on_commit_callbacks(execute=True):
            log = dispatch_email(to_email="a@example.test", subject="Code", text_body=f"code {CODE}",
                                 connection="platform", stream="account", event="email_verification",
                                 audience="user", persist_body=False, sync=True, **kwargs)
    return log, delay, deliver


def test_request_returns_without_contacting_the_provider(django_capture_on_commit_callbacks):
    log, delay, deliver = _send(django_capture_on_commit_callbacks)
    deliver.assert_not_called()
    delay.assert_called_once()
    assert log.status == EmailLog.Status.PENDING and transient_mail.accepted(log)
    assert CODE not in delay.call_args.args[1]            # the broker only holds ciphertext
    assert CODE not in EmailLog.objects.get(pk=log.pk).text_body  # and the stored row stays redacted


def test_worker_delivers_once_and_a_duplicate_task_does_not_resend(django_capture_on_commit_callbacks):
    log, delay, _ = _send(django_capture_on_commit_callbacks)
    sealed = delay.call_args.args[1]

    def fake_deliver(row):
        assert row.text_body == f"code {CODE}" and row.to_email == "a@example.test"
        EmailLog.objects.filter(pk=row.pk).update(status=EmailLog.Status.SENT)
        return row
    with patch("apps.integrations.dispatch._deliver", side_effect=fake_deliver) as deliver, \
            patch("apps.integrations.notification_cutover.sending_allowed", return_value=True):
        deliver_transient_email_task.apply(args=[log.pk, sealed])
        deliver_transient_email_task.apply(args=[log.pk, sealed])
    assert deliver.call_count == 1


def test_tampered_or_expired_payload_fails_closed():
    assert transient_mail.unseal("not-a-token") is None
    sealed = transient_mail.seal({"to": "a@example.test"})
    with patch.object(transient_mail, "TTL_SECONDS", -1):
        assert transient_mail.unseal(sealed) is None


def test_operator_test_send_free_profile_and_eager_stay_inline(settings):
    assert transient_mail.queue_allowed("email_verification") is True
    assert transient_mail.queue_allowed("email_test") is False
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    assert transient_mail.queue_allowed("email_verification") is False
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    assert transient_mail.queue_allowed("email_verification") is False


def test_sms_code_is_queued_in_a_worker_install_and_inline_when_eager(django_capture_on_commit_callbacks, settings):
    from apps.integrations import sms
    with patch("apps.integrations.tasks_transient.deliver_transient_sms_task.delay") as delay, \
            patch.object(sms, "send_sms_now") as now:
        with django_capture_on_commit_callbacks(execute=True):
            assert sms.send_sms(to="+14155550100", body=f"code {CODE}") is True
    now.assert_not_called()
    assert CODE not in delay.call_args.args[0]
    settings.CELERY_TASK_ALWAYS_EAGER = True
    with patch.object(sms, "send_sms_now", return_value="sent") as now:
        assert sms.send_sms(to="+14155550100", body="x") is True
    now.assert_called_once()


def test_key_is_hkdf_derived_with_its_own_label_never_the_raw_secret(settings):
    import base64
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    settings.SECRET_KEY = "s" * 50
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"spaceworks/transient-mail/v1").derive(b"s" * 50)
    from cryptography.fernet import Fernet
    sealed = transient_mail.seal({"n": 1})
    assert Fernet(base64.urlsafe_b64encode(derived)).decrypt(sealed.encode()) == b'{"n": 1}'
    other = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"other-purpose").derive(b"s" * 50)
    with pytest.raises(Exception):
        Fernet(base64.urlsafe_b64encode(other)).decrypt(sealed.encode())


def test_rotation_reads_messages_sealed_under_the_previous_key(settings):
    settings.TRANSIENT_MAIL_KEY = "old-" + "k" * 40
    sealed = transient_mail.seal({"code": CODE})
    settings.TRANSIENT_MAIL_KEY = "new-" + "k" * 40
    assert transient_mail.unseal(sealed) is None                      # old key no longer configured
    settings.TRANSIENT_MAIL_KEY_PREVIOUS = "old-" + "k" * 40
    assert transient_mail.unseal(sealed) == {"code": CODE}            # previous key still opens it
    assert transient_mail.unseal(transient_mail.seal({"n": 2})) == {"n": 2}  # new messages use the new key
    settings.TRANSIENT_MAIL_KEY_PREVIOUS = ""
    settings.SECRET_KEY_FALLBACKS = ["old-" + "k" * 40]
    assert transient_mail.unseal(sealed) == {"code": CODE}            # Django's own fallback list also works
