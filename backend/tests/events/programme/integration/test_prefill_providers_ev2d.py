from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.http import Http404
from django.utils import timezone

from apps.events.contracts.prefill_registration import EventPrefillContexts
from apps.events.contributions.models_roles import EventRolePosting
from tests.events.staff_grant_helpers import grant_fixture


def schema():
    return {"schema_version": 2, "form_id": "volunteer", "revision": 1, "questions": [
        {"id": "other", "type": "yes_no", "label": "Other?", "required": False},
        {"id": "institution", "type": "short_text", "label": "Institution", "required": False,
         "profile_field_key": "institution", "show_if": {"field_id": "other", "op": "eq", "value": True}},
    ]}


@pytest.mark.django_db
def test_role_prefill_has_no_membership_requirement_and_omits_conditional_values():
    space, _, member, event, _ = grant_fixture()
    space.enabled_features = [*space.enabled_features, "events.volunteering"]
    space.save(update_fields=["enabled_features"])
    posting = EventRolePosting.objects.create(event=event, makerspace=space, role="volunteer", title="Welcome crew",
        state="open", opens_at=timezone.now()-timedelta(days=1), closes_at=event.starts_at, form_schema=schema())
    selector = {"event_id": event.pk, "makerspace_id": space.pk,
                "subject_kind": "role_assignment", "posting_id": posting.pk}
    context = EventPrefillContexts().resolve(actor_id=member.pk, selector=selector)
    assert context.owner_id == member.pk and [q["id"] for q in context.questions] == ["other"]
    assert not member.makerspace_memberships.exists()
    with pytest.raises(Http404):
        EventPrefillContexts().resolve(actor_id=member.pk, selector={**selector, "makerspace_id": space.pk+1})
