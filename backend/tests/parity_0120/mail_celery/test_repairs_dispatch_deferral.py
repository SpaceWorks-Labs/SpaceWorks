"""Repair dispatch: the staff request validates and enqueues; the worker job does the provider sends."""
from unittest.mock import patch

from apps.maintenance.repairs import dispatch


def test_without_a_worker_the_sends_run_inline():
    with patch.object(dispatch, "defer_enabled", return_value=False), \
            patch.object(dispatch, "send_planned", return_value=["row"]) as send:
        assert dispatch.dispatch("actor", "issue", contact_ids=[1], channel_names=None, note="n") == ["row"]
    send.assert_called_once()


def test_send_planned_is_registered_for_the_worker():
    from apps.integrations.fanout_jobs import REGISTRY
    assert REGISTRY[f"{dispatch.send_planned.__module__}.send_planned"] is dispatch.send_planned
