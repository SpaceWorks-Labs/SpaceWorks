"""Typed FK grants preserve payment compatibility and reject post-issue changes."""
import pytest
from django.db import IntegrityError, transaction
from apps.integrations.notification_attachment_sources import AttachmentReference, DocumentDeliveryError, source_for
from tests.billing_docs.conftest import document, document_mail  # noqa: F401
from tests.billing_docs.test_r2_media import media, grant, model  # noqa: F401
from tests.p2_n_other.conftest import lane, payment  # noqa: F401

pytestmark = pytest.mark.django_db


def test_grant_binds_owner_revision_and_integration_generation(media):
    from apps.integrations.notification_media import consume_grant
    _, token = grant(media)
    row = model().objects.get(delivery=media.delivery)
    assert row.document_id == media.document.pk and row.certificate_id is None
    assert row.storage_makerspace_id == media.document.makerspace_id
    assert row.source_revision == media.envelope.revision
    assert row.recipient_id_snapshot == media.owner.pk
    assert row.integration_generation == media.delivery.integration_generation
    assert row.integration_identity == media.delivery.integration_identity
    model().objects.filter(pk=row.pk).update(source_revision="changed")
    assert consume_grant(token) is None


def test_origin_source_target_helper_declares_both_notification_and_storage_owners(media):
    from apps.integrations.notification_media import media_source_targets
    _, token = grant(media)
    assert media_source_targets(token) == {media.space.pk}
    assert model().objects.get(delivery=media.delivery).consumed_at is None


@pytest.mark.parametrize("field,value", [("recipient_id_snapshot", 999999), ("integration_generation", 999),
    ("integration_identity", "replaced")])
def test_grant_cannot_move_between_owner_or_provider_generations(media, field, value):
    from apps.integrations.notification_media import consume_grant
    _, token = grant(media)
    model().objects.filter(delivery=media.delivery).update(**{field: value})
    assert consume_grant(token) is None


def test_media_subject_check_refuses_a_subjectless_grant(media):
    with pytest.raises(IntegrityError), transaction.atomic():
        model().objects.create(delivery=media.delivery, token_digest="0" * 64,
            expires_at=media.delivery.created_at)


def test_source_registry_never_accepts_a_badge_or_generic_fk():
    from apps.integrations.notification_attachment_sources import AttachmentSource, register_source
    with pytest.raises(ValueError):
        register_source("events.badge", AttachmentSource(lambda _: (), lambda **kw: None,
            lambda **kw: None, "content_object"))
    with pytest.raises(DocumentDeliveryError):
        AttachmentReference("events.badge", 1, "badge", "1")


@pytest.mark.parametrize("change", ["rotation", "endpoint_revoked"])
def test_policy_change_during_storage_read_drops_bytes_but_keeps_one_use(media, monkeypatch, change):
    from django.utils import timezone
    from apps.integrations.notification_media import consume_grant
    _, token = grant(media)

    def render(*args, **kwargs):
        if change == "rotation":
            media.config.generation += 1
            media.config.save(update_fields=["generation"])
        else:
            media.endpoint.revoked_at = timezone.now()
            media.endpoint.save(update_fields=["revoked_at"])
        return "receipt.pdf", b"%PDF-private", "application/pdf"

    monkeypatch.setattr("apps.integrations.notification_media.render_attachment", render)
    assert consume_grant(token) is None
    assert model().objects.get(delivery=media.delivery).consumed_at is not None
    assert consume_grant(token) is None
