"""The preview reads the actual old schema without changing it."""
import io
import json

import pytest
from django.core.management import call_command

from tests.fixed_roles.migration_helpers import old_database, historical_world

pytestmark = pytest.mark.django_db(transaction=True)


def test_preview_prints_refusal_before_membership_outcomes(old_database):
    world = historical_world(old_database)
    model = old_database.get_model
    rule = model("integrations", "NotificationRecipient").objects.create(
        makerspace=world["space"], feature="maintenance", event="logged", kind="role",
        role=world["roles"]["typed"],
    )
    before = list(model("makerspaces", "MakerspaceRole").objects.order_by("pk").values())
    try:
        output = io.StringIO()
        call_command("preview_fixed_roles", makerspace=world["space"].pk, stdout=output, no_color=True)
        text = output.getvalue()
        assert text.startswith("must fix before upgrading:")
        assert text.index(f"recipient={rule.pk}") < text.index("Membership ")
        for membership in world["memberships"].values():
            assert f"Membership {membership.pk} " in text
        assert "machine_manager_dropped: machine-only scope" in text
        assert "dropped_machine_ids" in text
        assert "E1" in text and "E2" in text
        assert list(model("makerspaces", "MakerspaceRole").objects.order_by("pk").values()) == before
    finally:
        model("integrations", "NotificationRecipient").objects.filter(pk=rule.pk).delete()


def test_json_contains_structured_per_membership_scope_evidence(old_database):
    world = historical_world(old_database)
    output = io.StringIO()
    call_command("preview_fixed_roles", as_json=True, makerspace=world["space"].pk, stdout=output)
    result = json.loads(output.getvalue())
    assert next(iter(result)) == "must fix before upgrading"
    assert result["must fix before upgrading"] == []
    assert set(result) == {"must fix before upgrading", "makerspaces", "memberships", "requests", "invitations", "schedules"}
    rows = {row["id"]: row for row in result["memberships"]}
    typed = rows[world["memberships"]["typed"].pk]
    assert typed["to_roles"] == ["machine_manager"]
    assert typed["machine_scope"]["to"] == {"types": [world["kind"].pk], "machines": []}
    assert typed["machine_scope"]["dropped_machine_ids"] == [world["machine"].pk]
    assert rows[world["memberships"]["legacy"].pk]["primary_slug"] is None
