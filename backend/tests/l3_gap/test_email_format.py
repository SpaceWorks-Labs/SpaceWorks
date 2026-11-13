"""P22 / #132h: "your card" email as the holder's choice of PDF or PNG images, remembered for
staff and bulk sends, rendered at send time through the typed, email-only attachment source."""
import pytest

from apps.audit.models import AuditLog
from apps.card_designs import email_delivery
from apps.card_designs.email import send_card_email
from apps.integrations.notification_attachment_sources import AttachmentReference, DocumentDeliveryError
from apps.integrations.notification_attachment_sources import render_attachment
from apps.makerspaces import member_card_services as services
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db


def _card(slug):
    space = card_space(slug)
    sm = manager(space)
    user, membership = member(space)
    return space, sm, user, services.issue_card(sm, membership)


def test_parse_kind_keeps_old_pdf_references_and_refuses_unknown_shapes():
    assert email_delivery.parse_kind("member_card") == ("member_card", "pdf", "front")
    assert email_delivery.parse_kind("event_card:png:back") == ("event_card", "png", "back")
    assert email_delivery.parse_kind("member_card:gif:front") == (None, None, None)
    assert email_delivery.parse_kind("member_card:png:middle") == (None, None, None)


def test_holder_chooses_png_in_settings_and_it_is_audited():
    _space, _sm, user, card = _card("gap-ef-settings")
    api = client(user)
    url = f"/api/v1/member/cards/member_card/{card.pk}/settings"
    assert api.get(url).json()["email_format"] == "pdf"
    assert api.patch(url, {"email_format": "png"}, format="json").json()["email_format"] == "png"
    card.refresh_from_db()
    assert card.email_format == "png"
    assert AuditLog.objects.filter(action="card.email_format_changed", meta__format="png").exists()
    assert api.patch(url, {"email_format": "gif"}, format="json").status_code == 400


def test_email_me_with_a_format_remembers_it_and_queues_png_references():
    from apps.integrations.models import EmailLog
    _space, _sm, user, card = _card("gap-ef-send")
    response = client(user).post(f"/api/v1/member/cards/member_card/{card.pk}/email", {"format": "png"},
                                 format="json")
    assert response.status_code == 202, response.content
    card.refresh_from_db()
    assert card.email_format == "png"
    log = EmailLog.objects.get(source_kind="card_designs.card")
    assert log.source_metadata["format"] == "png"
    kinds = [kind for kind, _revision in email_delivery.references_for("member_card", card)]
    assert kinds[0] == "member_card:png:front" and all(kind.startswith("member_card:png:") for kind in kinds)


def test_pdf_stays_the_default_reference():
    _space, _sm, _user, card = _card("gap-ef-default")
    assert email_delivery.references_for("member_card", card) == (("member_card", email_delivery.revision(card)),)


def test_png_attachment_renders_for_the_holder_only():
    space, _sm, user, card = _card("gap-ef-render")
    card.email_format = "png"
    card.save(update_fields=["email_format"])
    reference = AttachmentReference("card_designs.card", card.pk, "member_card:png:front",
                                    email_delivery.revision(card))
    filename, data, content_type = render_attachment(reference, makerspace_id=space.pk, recipient_id=user.pk)
    assert content_type == "image/png" and filename.endswith("-front.png") and data.startswith(b"\x89PNG")
    with pytest.raises(DocumentDeliveryError):
        render_attachment(reference, makerspace_id=space.pk, recipient_id=user.pk + 999)
    bad = AttachmentReference("card_designs.card", card.pk, "member_card:png:middle", email_delivery.revision(card))
    with pytest.raises(DocumentDeliveryError):
        render_attachment(bad, makerspace_id=space.pk, recipient_id=user.pk)


def test_staff_send_uses_the_holders_choice():
    from apps.integrations.models import EmailLog
    _space, sm, _user, card = _card("gap-ef-staff")
    card.email_format = "png"
    card.save(update_fields=["email_format"])
    assert send_card_email("member_card", card, actor=sm, explicit=True)
    assert EmailLog.objects.get(source_kind="card_designs.card").source_metadata["format"] == "png"
