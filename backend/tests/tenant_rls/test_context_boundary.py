"""A1 context boundary: one binding per request/task/command, reset in finally, never leaked."""

import pytest
from django.db import connection, transaction
from django.test import RequestFactory
from django.urls import resolve, reverse

from apps.tenant_rls import boundary
from apps.tenant_rls.context import Binding, capability_context, current, tenant_context
from apps.tenant_rls.wrapper import prefix

from .conftest import labels, setting

pytestmark = pytest.mark.django_db


def test_tenant_binding_hides_other_tenants_and_open_sees_all(probe, boxes):
    a = boxes[0].makerspace
    assert labels() == ["A box", "B box"]
    with tenant_context(a.pk):
        assert labels() == ["A box"]
    assert labels() == ["A box", "B box"]


def test_binding_and_settings_reset_after_an_exception(probe, boxes):
    a = boxes[0].makerspace
    with pytest.raises(RuntimeError):
        with tenant_context(a.pk):
            assert labels() == ["A box"]
            raise RuntimeError("boom")
    assert current() is None
    assert setting("app.rls_bound") == "" and setting("app.makerspace_id") == ""
    assert labels() == ["A box", "B box"]


def test_innermost_binding_wins_and_the_outer_one_returns(probe, boxes):
    a = boxes[0].makerspace
    with tenant_context(a.pk):
        with capability_context("backup", label="test"):
            assert labels() == ["A box", "B box"]
        assert labels() == ["A box"]


def test_savepoint_rollback_inside_a_binding_keeps_the_scope(probe, boxes):
    from apps.boxes.models import Box
    a = boxes[0].makerspace
    with tenant_context(a.pk):
        with pytest.raises(Exception):
            with transaction.atomic():
                Box.objects.create(makerspace=a, label="A box", code=boxes[0].code)  # unique code clash
        assert labels() == ["A box"]


def test_server_side_cursor_is_scoped_then_reset(probe, boxes):
    from apps.boxes.models import Box
    a = boxes[0].makerspace
    with tenant_context(a.pk), transaction.atomic():
        seen = sorted(box.label for box in Box.objects.filter(label__in=["A box", "B box"]).iterator(chunk_size=1))
    assert seen == ["A box"]
    assert setting("app.rls_bound") == ""


def test_prefix_carries_only_validated_values():
    binding = Binding(scope=frozenset({3, 7}))
    text = prefix(binding, "enforce")
    assert "set_config('app.makerspace_id', '3,7', true)" in text and "set_config('app.rls_bound', 'on', true)" in text
    with pytest.raises(ValueError):
        prefix(Binding(capability="x'; DROP TABLE y; --"), "enforce")


@pytest.mark.django_db(transaction=True)
def test_autocommit_statements_leave_nothing_on_a_reused_connection(probe, settings):
    from apps.makerspaces.models import Makerspace
    settings.CONN_MAX_AGE = 60
    space = Makerspace.objects.create(name="RLS pooled", slug="rls-pooled")
    assert connection.get_autocommit()
    with tenant_context(space.pk):
        assert Makerspace.objects.filter(pk=space.pk).exists()
        # Under autocommit the settings died with the statement: nothing persists on the session.
        assert setting("app.rls_bound") == ""
    assert setting("app.makerspace_id") == ""


def _request(name, **kwargs):
    request = RequestFactory().get(reverse(name, kwargs=kwargs))
    request.resolver_match = resolve(request.path_info)
    request.user = None
    return request


def test_request_boundary_binds_a_tenant_addressed_route(spaces):
    a = spaces[0]
    binding = boundary.request_binding(_request("admin-makerspace-key-events", makerspace_id=a.pk))
    assert binding.scope == frozenset({a.pk}) and not binding.capability


def test_request_boundary_binds_control_and_registered_routes(spaces):
    request = RequestFactory().get("/control/")
    request.resolver_match = None
    request.user = None
    assert boundary.request_binding(request).capability == "platform_console"
    restore = boundary.request_binding(_request("admin-makerspace-restores", makerspace_id=spaces[0].pk))
    assert restore.capability == "per_space_restore"


def test_request_boundary_leaves_unaddressed_routes_open():
    assert boundary.request_binding(_request("public-makerspaces")).capability == "public_directory"
    request = RequestFactory().get("/api/v1/health/")
    request.resolver_match = resolve("/api/v1/health/")
    request.user = None
    assert boundary.request_binding(request) is None


def test_middleware_resets_the_binding_after_the_request(probe, client, spaces):
    client.get(reverse("admin-makerspace-key-events", kwargs={"makerspace_id": spaces[0].pk}))
    assert current() is None
    assert setting("app.rls_bound") == ""


def test_task_boundary_binds_and_releases(spaces):
    class Task:
        name = "tests.tenant_rls.fake"

        @staticmethod
        def run(makerspace_id, other=None):
            return None

    boundary.on_task_prerun(task_id="t1", task=Task, args=(spaces[0].pk,), kwargs={})
    assert current().scope == frozenset({spaces[0].pk})
    boundary.on_task_postrun(task_id="t1", task=Task)
    assert current() is None
    Task.name = "apps.backup.tasks_space_restore.run_space_restore_apply_task"
    boundary.on_task_prerun(task_id="t2", task=Task, args=(), kwargs={})
    assert current().capability == "per_space_restore"
    boundary.on_task_postrun(task_id="t2", task=Task)
    assert current() is None


def test_fanout_tenant_write_binds_its_tenant(probe, boxes):
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    a = boxes[0].makerspace
    with fanout_tenant_write(a.pk, operation="test", counts={}) as admitted:
        assert admitted
        assert current().scope == frozenset({a.pk})
        assert labels() == ["A box"]
    assert current() is None


def test_management_commands_run_open(probe, boxes, capsys):
    from django.core.management import call_command
    call_command("rls_status")
    out = capsys.readouterr().out
    assert "mode=enforce" in out and "missing_or_stale=0" in out
    assert labels() == ["A box", "B box"]
