from django.db import IntegrityError, connection, transaction
from tests.accounts.account_factories import make_staff as staff_account
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import User
from apps.accounts.rbac import Action
from apps.audit.models import AuditLog
from apps.integrations.email_templates import render, render_preview
from apps.integrations.email_streams import TYPE_OVERRIDABLE_AUDIENCES
from apps.integrations.email_templates_registry import REGISTRY, get_entry
from apps.integrations.models import EmailTemplate, MachineTypeEmailTemplate
from apps.machines.models import (
    Machine,
    MachineType,
)
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole

pytestmark = pytest.mark.django_db


def space(slug):
    row = Makerspace.objects.create(name=slug, slug=slug)
    row.enabled_modules = sorted(set(row.enabled_modules or []) | {"maintenance"})
    row.save(update_fields=["enabled_modules"])
    return row


def custom_type(makerspace, slug):
    return MachineType.objects.create(makerspace=makerspace, slug=slug, name=slug.title())


@transaction.atomic
def actor_for(makerspace, username, actions, *, types=()):
    from tests.fixed_roles.helpers import roles_for_actions, assign_builtin_roles

    roles = roles_for_actions(makerspace, actions)
    actor = staff_account(makerspace, username=username, email=f"{username}@example.test",
                          role_slug=roles[0].slug, access_status="active")
    assign_builtin_roles(actor, makerspace, *(role.slug for role in roles), machine_types=types)
    return actor


def client_for(actor):
    client = APIClient()
    client.force_authenticate(user=actor)
    return client


def list_url(makerspace):
    return f"/api/v1/admin/makerspace/{makerspace.pk}/email-templates"


def detail_url(makerspace, stream, audience, key, machine_type=None):
    base = f"{list_url(makerspace)}/{stream}/{audience}/{key}"
    return f"{base}/types/{machine_type.pk}" if machine_type else base


def rendered_default(key, stream="maintenance", audience="staff"):
    """The registry default as RENDERED output, which is what `render` returns.

    `render_preview` renders the strings it is given against the entry's own
    `sample_context` -- the same context these tests pass in -- so this is the one honest
    expected value for "fell through to the registry".
    """
    entry = get_entry(stream, audience, key)
    return render_preview(
        stream, audience, key,
        entry.default_subject, entry.default_text, entry.default_html,
    )


def template(makerspace, machine_type, *, subject="Type subject", active=True):
    return MachineTypeEmailTemplate.objects.create(
        makerspace=makerspace, machine_type=machine_type, stream="maintenance",
        audience="staff", key="logged", subject=subject, text_body="Type body",
        is_active=active,
    )


def test_type_resolution_fallback_chain_and_dormant_none(django_assert_num_queries):
    makerspace = space("type-resolution")
    laser = custom_type(makerspace, "resolution-laser")
    entry = get_entry("maintenance", "staff", "logged")
    context = entry.sample_context
    EmailTemplate.objects.create(
        makerspace=makerspace, stream="maintenance", audience="staff", key="logged",
        subject="Space subject", text_body="Space body",
    )

    with django_assert_num_queries(1):
        unchanged = render(makerspace, "maintenance", "staff", "logged", context)
    assert unchanged["subject"] == "Space subject"

    template(makerspace, laser)
    assert render(makerspace, "maintenance", "staff", "logged", context,
                  machine_type=laser)["subject"] == "Type subject"

    MachineTypeEmailTemplate.objects.filter(machine_type=laser).update(is_active=False)
    assert render(makerspace, "maintenance", "staff", "logged", context,
                  machine_type=laser)["subject"] == "Space subject"

    MachineTypeEmailTemplate.objects.filter(machine_type=laser).update(
        is_active=True, subject="{% if %}"
    )
    assert render(makerspace, "maintenance", "staff", "logged", context,
                  machine_type=laser)["subject"] == "Space subject"

    # Both levels broken falls all the way to the registry. Compared against the RENDERED
    # default, not `entry.default_subject` -- the registry default is a template
    # (`{{ makerspace.name }} maintenance ...`) and `render` returns rendered strings, so
    # comparing the two can never match whatever the code does.
    EmailTemplate.objects.filter(makerspace=makerspace).update(subject="{% if %}")
    assert render(makerspace, "maintenance", "staff", "logged", context,
                  machine_type=laser)["subject"] == rendered_default("logged")["subject"]


def test_missing_override_and_foreign_type_are_inert():
    own = space("type-inert-own")
    foreign = space("type-inert-foreign")
    own_type = custom_type(own, "inert-own")
    foreign_type = custom_type(foreign, "inert-foreign")
    entry = get_entry("maintenance", "staff", "logged")
    template(foreign, foreign_type, subject="Foreign secret")

    without_row = render(
        own, "maintenance", "staff", "logged", entry.sample_context,
        machine_type=own_type,
    )
    foreign_supplied = render(
        own, "maintenance", "staff", "logged", entry.sample_context,
        machine_type=foreign_type,
    )

    expected = rendered_default("logged")["subject"]
    assert without_row["subject"] == expected
    assert foreign_supplied["subject"] == expected
    assert "Foreign secret" not in foreign_supplied.values()


def test_machine_type_model_refuses_dead_stream_and_foreign_type():
    own = space("type-clean-own")
    foreign = space("type-clean-foreign")
    row = template(own, custom_type(foreign, "clean-foreign"))
    with pytest.raises(ValidationError):
        row.full_clean()
    row.machine_type = custom_type(own, "clean-own")
    row.stream = "hardware"
    with pytest.raises(ValidationError):
        row.full_clean()


def test_scoped_authority_matrix_and_dead_coordinates():
    makerspace = space("type-authority")
    laser = custom_type(makerspace, "authority-laser")
    kiln = custom_type(makerspace, "authority-kiln")
    foreign_type = custom_type(space("type-authority-foreign"), "authority-foreign")
    printer = MachineType.objects.get(makerspace__isnull=True, slug="3d_printer")
    machine = Machine.objects.create(makerspace=makerspace, machine_type=laser, name="One laser")
    none = actor_for(makerspace, "type-none", [Action.MANAGE_MACHINES])
    one = actor_for(makerspace, "type-one", [Action.MANAGE_MACHINES], types=[laser])
    both = actor_for(makerspace, "type-both", [Action.MANAGE_MACHINES], types=[laser, kiln])
    assert client_for(none).get(list_url(makerspace)).status_code == 404
    for actor, expected in ((one, {laser.pk}), (both, {laser.pk, kiln.pk})):
        response = client_for(actor).get(list_url(makerspace))
        assert response.status_code == 200
        maintenance = [row for row in response.data if row["stream"] == "maintenance"]
        assert {item["id"] for row in maintenance for item in row["overridable_types"]} == expected
        assert {row["audience"] for row in maintenance} == {"staff"}
        assert all(row["can_edit_space_default"] is False for row in maintenance)
        assert "printing" not in {row["stream"] for row in response.data}
        assert "certifications" not in {row["stream"] for row in response.data}
        assert client_for(actor).get(detail_url(
            makerspace, "certifications", "staff", "granted"
        )).status_code == 404
        assert client_for(actor).get(detail_url(
            makerspace, "maintenance", "staff", "logged"
        )).status_code == 404

    assert client_for(one).get(detail_url(
        makerspace, "maintenance", "staff", "logged", laser
    )).status_code == 200
    assert client_for(one).get(detail_url(
        makerspace, "maintenance", "staff", "logged", kiln
    )).status_code == 404
    assert client_for(one).get(detail_url(
        makerspace, "maintenance", "staff", "logged", foreign_type
    )).status_code == 404
    space_row = detail_url(makerspace, "maintenance", "staff", "logged")
    update = {"subject": "No", "text_body": "No", "html_body": "", "is_active": True}
    assert client_for(one).patch(space_row, update, format="json").status_code == 404
    assert client_for(one).post(f"{space_row}/reset").status_code == 404
    assert printer.pk not in {laser.pk, kiln.pk}




def test_null_primary_legacy_role_cannot_grant_email_template_access():
    makerspace = space("type-unrestricted-actors")
    legacy = staff_account(makerspace, username="type-legacy-machine", role_slug="machine_manager")
    membership = MakerspaceMembership.staff_tracks.get(user=legacy, makerspace=makerspace)
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=membership.pk).update(assigned_role=None)
        assert client_for(legacy).get(list_url(makerspace)).status_code == 404
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    superadmin = User.objects.create_superuser(username="type-superadmin", email="super@example.test")
    response = client_for(superadmin).get(list_url(makerspace))
    assert response.status_code == 200
    machine_rows = [row for row in response.data if row["stream"] in {"printing", "maintenance"}]
    assert machine_rows
    assert all(row["can_edit_space_default"] is True for row in machine_rows)


def test_type_patch_reset_fallback_and_audit_metadata():
    makerspace = space("type-api-mutation")
    laser = custom_type(makerspace, "mutation-laser")
    actor = actor_for(makerspace, "type-mutation-actor", [Action.MANAGE_MACHINES], types=[laser])
    EmailTemplate.objects.create(
        makerspace=makerspace, stream="maintenance", audience="staff", key="logged",
        subject="Space fallback", text_body="Space fallback body",
    )
    url = detail_url(makerspace, "maintenance", "staff", "logged", laser)
    payload = {"subject": "Laser wording", "text_body": "Laser body",
               "html_body": "", "is_active": True}
    patched = client_for(actor).patch(url, payload, format="json")
    assert patched.status_code == 200
    assert patched.data["is_overridden"] is True
    assert patched.data["default_subject"] == "Space fallback"
    reset = client_for(actor).post(f"{url}/reset")
    assert reset.status_code == 200
    assert reset.data["is_overridden"] is False
    assert reset.data["subject"] == "Space fallback"
    logs = AuditLog.objects.filter(action__in=[
        "email_template.type_updated", "email_template.type_reset"
    ]).order_by("created_at")
    assert [row.meta for row in logs] == [
        {"stream": "maintenance", "audience": "staff", "key": "logged",
         "machine_type_id": laser.pk},
        {"stream": "maintenance", "audience": "staff", "key": "logged",
         "machine_type_id": laser.pk},
    ]
    assert all("body" not in str(row.meta).lower() for row in logs)


def test_custom_type_deletion_cascades_override():
    makerspace = space("type-delete-cascade")
    laser = custom_type(makerspace, "delete-laser")
    row = template(makerspace, laser)
    laser.delete()
    assert not MachineTypeEmailTemplate.objects.filter(pk=row.pk).exists()


def test_mixed_role_keeps_streams_machine_scoping_has_no_say_over():
    """A scoped maintainer who ALSO holds another stream's action keeps that stream.

    Memberships can combine Inventory or Event Manager
    with a type-scoped Machine Manager role. Narrowing every stream rather than only the
    machine-bearing ones revoked those independent grants outright: a non-machine stream
    has no firing types, so "narrowed" collapsed to "reaches nothing" and the stream
    vanished from the list and 404'd on its own space-level row. Same mixed-role rule as
    the dashboard's non-machine counters.
    """
    makerspace = space("mixed-role")
    laser = custom_type(makerspace, "laser")
    actor = actor_for(
        makerspace,
        "inventory-and-laser",
        [Action.EDIT_INVENTORY, Action.MANAGE_EVENTS, Action.MANAGE_MACHINES],
        types=[laser],
    )
    client = client_for(actor)

    rows = client.get(list_url(makerspace)).json()
    streams = {row["stream"] for row in rows}
    assert "hardware" in streams, "EDIT_INVENTORY must still reach the hardware stream"
    assert "events" in streams, "MANAGE_EVENTS must still reach the events stream"

    # Those streams keep their space-level default; only the machine-bearing stream is narrowed.
    for row in rows:
        if row["stream"] in {"hardware", "events"}:
            assert row["can_edit_space_default"] is True
            assert row["overridable_types"] == []
        if row["stream"] == "maintenance":
            assert row["can_edit_space_default"] is False

    assert client.get(detail_url(makerspace, "hardware", "requester", "request_received")).status_code == 200
    assert client.patch(
        detail_url(makerspace, "hardware", "requester", "request_received"),
        {"subject": "Mixed subject", "text_body": "Body", "html_body": "", "is_active": True},
        format="json",
    ).status_code == 200
    # ...while the maintenance space default stays refused.
    assert client.get(detail_url(makerspace, "maintenance", "staff", "logged")).status_code == 404


def test_list_resolves_firing_types_per_coordinate_not_per_registry_key():
    """`MachineType` reads must scale with COORDINATES, not with notification events.

    Resolving `_firing_type_queryset` inside the entry loop issued one read per registry
    key -- 18 across printing and maintenance as the registry stands -- so every event
    added made this endpoint slower for no new information. The firing types vary by
    (stream, audience) only. Asserted on the `machines_machinetype` reads specifically
    rather than a total query budget, because this endpoint carries unrelated per-stream
    cost that predates the type layer and a bare total would not say what it means.
    """
    makerspace = space("type-query-budget")
    for slug in ("budget-laser", "budget-kiln", "budget-mill"):
        custom_type(makerspace, slug)
    actor = actor_for(makerspace, "budget-manager", [Action.MANAGE_MAKERSPACE])

    with CaptureQueriesContext(connection) as captured:
        response = client_for(actor).get(list_url(makerspace))

    assert response.status_code == 200
    type_reads = [q for q in captured.captured_queries if "machines_machinetype" in q["sql"]]
    overridable_keys = sum(
        1 for (stream, audience, _key) in REGISTRY
        if audience in TYPE_OVERRIDABLE_AUDIENCES.get(stream, ())
    )
    assert overridable_keys >= 18, "registry shrank; this budget assumed many keys per coordinate"
    assert len(type_reads) <= 6, (
        f"{len(type_reads)} MachineType reads for {overridable_keys} overridable keys -- "
        "firing types are being resolved per key again"
    )
