"""O-B4: only join answers marked printable reach the card, as {{field:<key>}}."""
import json

import pytest

from apps.card_designs.holders_member_answers import printable_values, tag_key
from apps.forms_schema.schema_v2 import validate_schema
from apps.makerspaces.models import MembershipRequest
from tests.l3_local.helpers import card_space, member

pytestmark = pytest.mark.django_db


def test_tag_key_is_the_lower_snake_form_of_the_question_id():
    assert tag_key("Blood-Group") == "blood_group"


def test_schema_refuses_printable_on_sensitive_or_compound_questions():
    base = {"id": "q1", "type": "short_text", "label": "Chapter", "required": False}
    for extra in ({"type": "date_of_birth"}, {"sensitive": True}):
        with pytest.raises(Exception):
            validate_schema({"form_id": "f", "revision": 1, "questions": [{**base, **extra, "printable": True}]})


def test_only_printable_answers_print():
    space = card_space("pa-print")
    _user, membership = member(space)
    schema = {"version": 2, "form_id": "f", "revision": 1, "questions": [
        {"id": "chapter", "type": "short_text", "label": "Chapter", "required": False, "printable": True},
        {"id": "secret", "type": "short_text", "label": "Secret", "required": False}]}
    answers = {"version": 2, "answers": [
        {"id": "chapter", "label": "Chapter", "type": "short_text", "value": "Kochi"},
        {"id": "secret", "label": "Secret", "type": "short_text", "value": "hidden"}]}
    MembershipRequest.objects.create(makerspace=space, user=membership.user, kind="request", state="active",
                                     application_schema=schema, application_answers=json.dumps(answers))
    assert printable_values(membership) == {"field:chapter": "Kochi"}
