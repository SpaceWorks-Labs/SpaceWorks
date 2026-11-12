"""Decision 308(c): the one-off upgrade backfill gives existing accounts their username as handle when it is
valid and free; everyone else keeps the blocking "Choose your username" step. Idempotent."""
from io import StringIO

import pytest
from django.core.management import call_command

from apps.makerspaces.models import PublicHandle
from apps.makerspaces.public_profile_handles import claim_for_signup

from .conftest import make_person

pytestmark = pytest.mark.django_db


def _handleless(username, **fields):
    user = make_person(username, **fields)
    PublicHandle.objects.filter(user=user).delete()
    return user


def _run():
    out = StringIO()
    call_command("claim_default_handles", stdout=out)
    return out.getvalue()


def test_valid_free_usernames_are_claimed_and_the_rest_are_left_to_choose():
    free = _handleless("free-maker")
    short = _handleless("shorty")
    short.username = "ab"  # not a valid handle: never replaced by a generated one (305 addendum)
    short.save(update_fields=["username"])
    keeper = make_person("kept-handle")
    claim_for_signup(keeper, "chosen-name")  # already chose a different handle: untouched

    output = _run()

    assert PublicHandle.objects.get(user=free).handle == "free-maker"
    assert not PublicHandle.objects.filter(user=short).exists()
    assert PublicHandle.objects.get(user=keeper).handle == "chosen-name"
    assert output.startswith("Handles claimed: ") and "left to choose at sign-in: " in output


def test_walk_in_accounts_are_skipped_and_a_second_run_changes_nothing():
    walk_in = _handleless("walk-in-person")
    walk_in.is_walk_in = True
    walk_in.save(update_fields=["is_walk_in"])
    _handleless("second-maker")

    _run()
    assert not PublicHandle.objects.filter(user=walk_in).exists()
    count = PublicHandle.objects.count()
    assert "Handles claimed: 0" in _run()
    assert PublicHandle.objects.count() == count
