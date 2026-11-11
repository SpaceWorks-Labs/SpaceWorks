"""O-B2: join-form extras (photo / phone / state per plan) and section headings in the form schema."""
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from apps.forms_schema.schema_items_static import reanchor_sections, schema_items
from apps.forms_schema.validation import validate_answers, validate_form_schema
from apps.makerspaces import membership_join_fields as join_fields
from apps.makerspaces.membership_plan_policy import public_schema
from apps.makerspaces.models import MembershipPlan, MembershipRecord, MembershipRequest
from tests.makerspaces.l4_helpers import features_on
from tests.makerspaces.test_membership_admission_matrix import _setup

pytestmark = pytest.mark.django_db(transaction=True)


def _schema(**extra):
    questions = [
        {"id": "name", "type": "short_text", "label": "Name", "required": True},
        {"id": "why", "type": "long_text", "label": "Why", "required": False},
        {"id": "staff", "type": "short_text", "label": "Staff only", "required": False, "visibility": "server"},
    ]
    return {"schema_version": 2, "form_id": "join", "revision": 1, "questions": questions, **extra}


def test_sections_are_validated_anchored_headings_that_never_become_answers():
    schema = validate_form_schema(_schema(sections=[{"id": "about", "before": "name", "heading": " About you "}]))
    assert schema["sections"] == [{"id": "about", "before": "name", "heading": "About you"}]
    assert [item["kind"] for item in schema_items(schema)] == ["section", "question", "question", "question"]
    snapshot = validate_answers(schema, {"name": "Asha"})
    assert [row["id"] for row in snapshot["answers"]] == ["name"]
    with pytest.raises(Exception):
        validate_answers(schema, {"about": "x"})  # a heading id is not a question id


@pytest.mark.parametrize("sections", [
    [{"id": "a", "before": "missing", "heading": "X"}],
    [{"id": "name", "before": "name", "heading": "X"}],
    [{"id": "a", "before": "name", "heading": " "}],
    [{"id": "a", "before": "name", "heading": "X"}, {"id": "a", "before": "why", "heading": "Y"}],
    [{"id": "a", "before": "name", "heading": "X", "extra": 1}],
])
def test_bad_sections_are_refused(sections):
    with pytest.raises(DjangoValidationError):
        validate_form_schema(_schema(sections=sections))


def test_a_schema_without_sections_is_unchanged_and_public_view_reanchors_headings():
    plain = validate_form_schema(_schema())
    assert "sections" not in plain and schema_items(plain)[0]["kind"] == "question"
    schema = validate_form_schema(_schema(sections=[{"id": "s1", "before": "staff", "heading": "Staff"},
                                                    {"id": "s2", "before": "why", "heading": "More"}]))
    visible = public_schema(schema)
    assert [question["id"] for question in visible["questions"]] == ["name", "why"]
    assert visible["sections"] == [{"id": "s2", "before": "why", "heading": "More"}]  # s1 had nothing left below it
    assert reanchor_sections(schema, schema["questions"]) == schema["sections"]


def _plan(space, **modes):
    plan = MembershipPlan.objects.filter(makerspace=space).first()
    for key, value in modes.items():
        setattr(plan, key, value)
    plan.save()
    return plan


def test_modes_are_off_until_the_switches_are_on_and_required_means_required():
    space, actor, applicant, plan, _ = _setup("approval")
    plan = _plan(space, join_photo="required", join_phone="required", join_state="optional")
    assert join_fields.modes(space, plan) == {"photo": "off", "phone": "hidden", "state": "hidden"}
    assert join_fields.clean(space, plan, None) is None  # nothing asked while the switches are off
    with pytest.raises(ValidationError):
        join_fields.clean(space, plan, {"phone": "+919800000000"})  # refused, not silently dropped
    features_on(space, "join_contact_fields")
    assert join_fields.modes(space, plan) == {"photo": "off", "phone": "required", "state": "optional"}
    with pytest.raises(ValidationError) as error:
        join_fields.clean(space, plan, {})
    assert "phone" in error.value.detail["join_fields"]
    assert join_fields.clean(space, plan, {"phone": "+91 98000 00000", "state_code": "29"}) == {
        "phone": "+919800000000", "state_code": "29"}
    with pytest.raises(ValidationError):
        join_fields.clean(space, plan, {"phone": "+919800000000", "state_code": "ABC"})
    with pytest.raises(ValidationError):
        join_fields.clean(space, plan, {"phone": "+919800000000", "surprise": 1})


def test_resubmission_keeps_a_required_value_already_on_file():
    space, actor, applicant, plan, _ = _setup("approval")
    plan = _plan(space, join_phone="required")
    features_on(space, "join_contact_fields")
    assert join_fields.clean(space, plan, {}, existing={"phone": "+919800000000"}) == {"phone": "+919800000000"}


def _activate_with(space, actor, applicant, extras):
    from apps.makerspaces import membership_services
    from apps.makerspaces.membership_helpers import _member_role
    membership_services.request_membership(applicant, space)
    row = MembershipRequest.objects.get(makerspace=space, user=applicant)
    row.application_answers = join_fields.encode(None, None, extras)
    row.save(update_fields=["application_answers"])
    return membership_services.approve_request(actor, row, _member_role(space))


def test_phone_and_state_reach_the_member_only_where_nothing_is_recorded_yet():
    space, actor, applicant, plan, _ = _setup("approval")
    features_on(space, "records")
    membership = _activate_with(space, actor, applicant, {"phone": "+919800000000", "state_code": "29"})
    applicant.refresh_from_db()
    assert applicant.phone == "+919800000000" and applicant.phone_e164 == ""  # never the verified login identity
    assert MembershipRecord.objects.get(membership=membership).state_code == "29"


def test_an_existing_phone_is_never_overwritten():
    space, actor, applicant, plan, _ = _setup("approval")
    applicant.phone = "keep-me"
    applicant.save(update_fields=["phone"])
    membership = _activate_with(space, actor, applicant, {"phone": "+919800000000"})
    applicant.refresh_from_db()
    assert applicant.phone == "keep-me" and membership.pk


_PHOTO = {"object_key": "member-cards/{space}/abc", "content_type": "image/png", "consent_at": "2026-11-11T00:00:00Z"}


def test_the_join_photo_never_replaces_a_photo_the_card_already_has():
    from apps.makerspaces.member_card_services import issue_card
    from apps.makerspaces.models import MemberCard
    space, actor, applicant, plan, _ = _setup("approval")
    photo = {**_PHOTO, "object_key": _PHOTO["object_key"].format(space=space.pk)}
    membership = _activate_with(space, actor, applicant, {"photo": photo})
    card = issue_card(actor, membership)
    MemberCard.objects.filter(pk=card.pk).update(photo_object_key="member-cards/1/existing")
    card.refresh_from_db()
    with patch("apps.evidence.storage.delete_object") as dropped, \
            patch("apps.makerspaces.member_card_storage.finalize_photo") as finalize:
        assert join_fields.apply_join_photo(card) is True
    finalize.assert_not_called()
    dropped.assert_called_once()
    card.refresh_from_db()
    assert card.photo_object_key == "member-cards/1/existing"
    row = MembershipRequest.objects.get(makerspace=space, user=applicant)
    assert join_fields.stored(row)["photo"]["applied"] is True
    assert join_fields.apply_join_photo(card) is False  # idempotent


def test_the_photo_is_attached_when_the_card_has_none():
    from apps.makerspaces.member_card_services import issue_card
    space, actor, applicant, plan, _ = _setup("approval")
    photo = {**_PHOTO, "object_key": _PHOTO["object_key"].format(space=space.pk)}
    membership = _activate_with(space, actor, applicant, {"photo": photo})
    card = issue_card(actor, membership)
    with patch("apps.makerspaces.member_card_storage.finalize_photo") as finalize:
        assert join_fields.apply_join_photo(card) is True
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["consent"] is True
