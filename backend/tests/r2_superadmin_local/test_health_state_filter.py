"""#185(7): filtering health cards by state also finds a state another one outranks."""
from apps.space_controls.health import has_state


def test_a_read_only_space_with_a_schedule_is_found_under_both():
    card = {"state": "scheduled", "read_only": {"at": "x"}, "archived_at": None, "schedule": {"archive_on": "x"}, "suspended": None}
    assert has_state(card, "scheduled") and has_state(card, "read_only")
    assert not has_state(card, "archived") and not has_state(card, "suspended")
