"""A finite managed writer keeps its retained session until the writer has exited.

Django's run_from_argv closes every connection when a command returns; the writer's
exit check then had to reconnect, which the retained-session guard forbids, so every
managed one-off writer (verify_storage, setup_instance, ...) failed after succeeding.
"""
from contextlib import contextmanager
from unittest.mock import patch

from django.db import connections

from apps.backup.managed import commands


def test_connections_close_only_after_the_writer_exit_check(monkeypatch):
    events = []

    @contextmanager
    def writer(category):
        events.append("enter")
        yield
        events.append("exit-check")

    def command(argv):
        connections.close_all()  # what run_from_argv does in its finally block
        events.append("command-done")

    monkeypatch.setenv("SPACEWORKS_DEPLOYMENT_MODE", "managed")
    with patch("apps.operations.cloud_runtime.writer", writer), patch("django.setup"), \
         patch.object(type(connections), "close_all", lambda self: events.append("closed")):
        commands.execute(["manage.py", "verify_storage"], command)
    assert events == ["enter", "command-done", "exit-check", "closed"]
    assert "close_all" not in vars(connections)


def test_non_writer_commands_are_untouched(monkeypatch):
    monkeypatch.setenv("SPACEWORKS_DEPLOYMENT_MODE", "managed")
    assert commands.execute(["manage.py", "check"], lambda argv: "ran") == "ran"
