"""Sender identity is a routeless email presentation policy, retaining the delivery log."""
from email.utils import parseaddr

import pytest
from django.core.mail import EmailMessage

from apps.integrations.models import EmailLog
from apps.integrations.space_sender import apply
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.payments.switch_helpers_cx11b_p2 import read_policy_cycle

pytestmark = [pytest.mark.django_db, pytest.mark.area_email, pytest.mark.area_notifications]


@pytest.mark.parametrize("key", ["email.sender_identity", "email"])
def test_saved_sender_identity_only_changes_display_name_and_reply_to_while_enabled(key):
    space = live_space("p2-sender", MODULE_KEYS)
    space.email_from_name, space.email_reply_to = "Retained sender", "desk@example.test"
    space.save(update_fields=["email_from_name", "email_reply_to"])
    log = EmailLog.objects.create(makerspace=space, to_email="recipient@example.test", subject="Retained subject",
        text_body="Retained text", feature="bookings", event="confirmed")
    def read():
        msg = EmailMessage("Subject", "Text", "Platform <delivery@example.test>", [log.to_email])
        apply(log, msg)
        return parseaddr(msg.from_email), msg.reply_to
    # The log's cached makerspace is the same instance being toggled.
    log.makerspace = space
    read_policy_cycle(space, {"log": log}, key, read,
        (("Retained sender", "delivery@example.test"), ["desk@example.test"]),
        (("Platform", "delivery@example.test"), []))
