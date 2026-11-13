"""The closed booking-decision intent: only the exact documented shape validates, in canonical key order."""

import pytest
from django.core.exceptions import ValidationError

from apps.separability.booking_decision_intent import canonical_intent, validate_intent

MESSAGE = "Invalid booking decision intent."


def good(**over):
    return {"version": 1, "makerspace_id": 1, "event_id": 2, "booking_id": 3, "creator_id": 4, "billing_owner": "booking", **over}


def test_canonical_intent_builds_the_closed_shape_in_sorted_key_order():
    intent = canonical_intent(makerspace_id=1, event_id=2, booking_id=3, creator_id=4)
    assert intent == good()
    assert list(intent) == ["billing_owner", "booking_id", "creator_id", "event_id", "makerspace_id", "version"]


def test_the_largest_safe_integer_is_accepted():
    assert validate_intent(good(event_id=9007199254740991))["event_id"] == 9007199254740991


@pytest.mark.parametrize("value", [None, [], "x", 5])
def test_a_non_object_is_refused(value):
    with pytest.raises(ValidationError, match=MESSAGE):
        validate_intent(value)


@pytest.mark.parametrize("mutation", [
    lambda d: d.pop("creator_id"), lambda d: d.update(extra=1), lambda d: d.update(version=2), lambda d: d.update(version=True),
    lambda d: d.update(version="1"), lambda d: d.update(billing_owner="member"),
])
def test_a_wrong_shape_version_or_owner_is_refused(mutation):
    value = good()
    mutation(value)
    with pytest.raises(ValidationError, match=MESSAGE):
        validate_intent(value)


@pytest.mark.parametrize("name", ["makerspace_id", "event_id", "booking_id", "creator_id"])
@pytest.mark.parametrize("bad", [0, -1, 9007199254740992, 1.5, "3", True, None])
def test_every_identifier_must_be_a_real_positive_safe_integer(name, bad):
    with pytest.raises(ValidationError, match=MESSAGE):
        validate_intent(good(**{name: bad}))
