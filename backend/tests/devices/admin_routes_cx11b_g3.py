"""Adapter administration: exact saved rows and audit deltas, never a 2xx-only proof."""
from uuid import uuid4

from apps.devices.models import (
    AdapterAccessLog, AdapterBinding, AdapterCommand, AdapterConfigVersion, AdapterCredential,
    AdapterTypeProfile, AdapterUsageLog, AdapterWebhook, AdapterWebhookDelivery, DeviceCommand, DeviceEvent, PrinterJob,
)
from tests.devices.route_world_cx11b_g3 import BASE_KEYS, command, credential, event, hook, printer_job, world
from tests.maintenance.route_support_cx11b_g3 import foreign_refusal, prove, send

OPS = ("list", "detail", "bind", "binding", "unbind", "command", "commands", "events", "config",
       "versions", "push", "hook", "hook_set", "hook_delete", "hook_rotate", "deliveries", "profile",
       "profile_set", "access", "usage", "jobs", "dispatch", "credentials", "credential_set", "credential_delete")


def keys(op):
    return (*BASE_KEYS, "machines.integrations.access") if op.startswith("credential") else BASE_KEYS


def run(op, key, native, monkeypatch):
    w = world(native)
    # Only the network boundary is replaced; auth, gates, serializers, DB and audits run.
    monkeypatch.setattr("apps.outbound_policy.is_public_https", lambda *a, **k: True)
    monkeypatch.setattr("apps.devices.tasks.deliver_adapter_webhook_task.delay", lambda *a, **k: None)
    name, args, method, body, status, audit = "", [w.device.pk], "get", {}, 200, None
    expected = None
    if op in {"list", "detail"}:
        name = "admin-adapter-list" if op == "list" else "admin-adapter-detail"
        args = [w.space.pk] if op == "list" else args
    elif op == "bind":
        name, method, status, audit = "admin-adapter-binding-create", "post", 201, "devices.adapter_bound"
        body = {"target_type": "space", "external_ref": "g3-new", "capabilities": ["events"]}
    elif op in {"binding", "unbind"}:
        name, args = "admin-adapter-binding-detail", [w.binding.pk]
        if op == "unbind":
            method, status, audit = "delete", 204, "devices.adapter_unbound"
    elif op in {"command", "commands"}:
        if op == "command":
            name, args, method, status, audit = "admin-adapter-binding-command", [w.binding.pk], "post", 201, \
                "devices.adapter_command_queued"
            body = {"capability": "control", "command": "pause", "params": {}}
        else:
            name, expected = "admin-adapter-commands", command(w)
    elif op == "events":
        name, expected = "admin-adapter-events", event(w)
    elif op == "config":
        name, args, method, audit = "admin-adapter-binding-config", [w.binding.pk], "put", "devices.adapter_config_set"
        body = {"auto_off_idle_minutes": 17, "require_area_clear": True}
    elif op in {"versions", "push"}:
        name = "admin-adapter-config-versions"
        expected = AdapterConfigVersion.objects.create(makerspace=w.space, device=w.device, version=1,
            config={"label": "retained"}, created_by=w.actor)
        if op == "push":
            method, status, audit, body = "post", 201, "devices.adapter_config_pushed", {"config": {"label": "new"}}
    elif op.startswith("hook") or op == "deliveries":
        expected = hook(w)
        name = "admin-adapter-webhook"
        if op == "hook_set":
            method, audit, body = "put", "devices.adapter_webhook_set", {"url": "https://hooks.example.test/new"}
        elif op == "hook_delete":
            method, status, audit = "delete", 204, "devices.adapter_webhook_disabled"
        elif op == "hook_rotate":
            name, method, audit = "admin-adapter-webhook-rotate", "post", "devices.adapter_webhook_rotated"
        elif op == "deliveries":
            name = "admin-adapter-webhook-deliveries"
            expected = AdapterWebhookDelivery.objects.create(makerspace=w.space, device=w.device,
                event_type="command.queued", envelope={"id": "retained"}, attempts=2)
    elif op.startswith("profile"):
        name, args = "admin-adapter-type-profile", [w.space.pk, w.machine.machine_type_id]
        expected = AdapterTypeProfile.objects.create(makerspace=w.space, machine_type=w.machine.machine_type,
                                                     config={"max_session_minutes": 42})
        if op == "profile_set":
            method, audit, body = "put", "devices.adapter_profile_set", {"max_session_minutes": 17}
    elif op == "access":
        name = "admin-adapter-access-decisions"
        expected = AdapterAccessLog.objects.create(makerspace=w.space, device=w.device, binding=w.binding,
            member=w.member, credential_type="pin", allowed=False, reason="no_session")
    elif op == "usage":
        name = "admin-adapter-usage"
        expected = AdapterUsageLog.objects.create(makerspace=w.space, device=w.device, binding=w.binding,
            operation_id=uuid4(), started_at=w.now, ended_at=w.now, active_minutes=7, outcome="completed")
    elif op in {"jobs", "dispatch"}:
        name, args = "admin-adapter-job-create", [w.binding.pk]
        if op == "jobs":
            expected = printer_job(w)
        else:
            method, status, audit, body = "post", 201, "devices.printer_job_created", {"service_request_id": w.job.pk}
    else:
        name, args = "admin-adapter-credentials", [w.space.pk]
        expected = credential(w)
        if op == "credential_set":
            method, status, audit = "post", 201, "devices.adapter_credential_set"
            body = {"user_id": w.member.pk, "kind": "pin", "secret": "837492", "label": "New PIN"}
        elif op == "credential_delete":
            name, args, method, audit = "admin-adapter-credential-detail", [expected.pk], "delete", \
                "devices.adapter_credential_removed"

    def check(response):
        data = response.data
        if op in {"list", "detail"}:
            records = data["results"] if op == "list" else [data]
            assert [(r["id"], r["name"]) for r in records] == [(str(w.device.pk), w.device.name)]
            assert [b["id"] for b in records[0]["bindings"]] == [str(w.binding.pk)]
        elif op == "bind":
            row = AdapterBinding.objects.get(pk=data["id"])
            assert (row.device_id, row.target_type, row.external_ref, row.capabilities) == (
                w.device.pk, "space", "g3-new", ["events"])
            assert AdapterBinding.objects.filter(device=w.device).count() == 2
        elif op == "binding":
            assert (data["id"], data["machine"]) == (str(w.binding.pk), w.machine.pk)
        elif op == "unbind":
            assert not AdapterBinding.objects.filter(pk=w.binding.pk).exists()
        elif op == "command":
            row = AdapterCommand.objects.get(pk=data["id"])
            assert (row.binding_id, row.capability, row.command, row.params, row.status) == (
                w.binding.pk, "control", "pause", {}, "queued")
            assert AdapterCommand.objects.filter(binding=w.binding).count() == 1
        elif op == "config":
            w.binding.refresh_from_db()
            assert w.binding.config == body
        elif op == "push":
            row = AdapterConfigVersion.objects.get(pk=data["id"])
            assert (row.version, row.config, row.created_by_id) == (2, {"label": "new"}, w.actor.pk)
            assert AdapterConfigVersion.objects.filter(device=w.device).count() == 2
        elif op in {"hook", "hook_set", "hook_delete", "hook_rotate"}:
            expected.refresh_from_db()
            assert expected.url == (body["url"] if op == "hook_set" else "https://hooks.example.test/old")
            assert expected.enabled is (op != "hook_delete")
            assert expected.secret_version == (2 if op == "hook_rotate" else 1)
            if op == "hook_rotate":
                from apps.devices.services_adapter_webhook import secret_for
                assert data["secret"] == secret_for(expected)
            elif op != "hook_delete":
                assert "secret" not in data
        elif op.startswith("profile"):
            expected.refresh_from_db()
            assert expected.config == {"max_session_minutes": 17 if op == "profile_set" else 42}
            assert data["config"] == expected.config
        elif op == "dispatch":
            row = PrinterJob.objects.get(pk=data["job_id"])
            assert (row.service_request_id, row.machine_id, row.device_id, row.state) == (
                w.job.pk, w.machine.pk, w.device.pk, "awaiting")
            assert row.command.kind == "adapter_job" and row.command.status == "queued"
            assert PrinterJob.objects.filter(service_request=w.job).count() == 1
            event_row = DeviceEvent.objects.get(device=w.device, event_type="printer_job_created")
            assert (event_row.command_id_snapshot, event_row.service_request_id_snapshot,
                    event_row.machine_id_snapshot) == (row.command_id, w.job.pk, w.machine.pk)
        elif op == "credential_set":
            from apps.devices.services_adapter_core import credential_digest
            row = AdapterCredential.objects.get(pk=data["id"])
            expected.refresh_from_db()
            assert expected.disabled_at is not None
            assert (row.user_id, row.label, row.digest) == (w.member.pk, "New PIN",
                credential_digest(w.space.pk, "pin", "837492", user_id=w.member.pk))
            assert AdapterCredential.objects.filter(user=w.member, disabled_at__isnull=True).count() == 1
            assert "digest" not in data and "secret" not in data
        elif op == "credential_delete":
            expected.refresh_from_db()
            assert expected.disabled_at is not None and data["disabled_at"] is not None
        else:
            records = data["results"] if isinstance(data, dict) else data
            assert [r["id"] for r in records] == [str(expected.pk)]
            fields = {"commands": ("command", "pause"), "events": ("event_type", "detection.reported"),
                "versions": ("config", {"label": "retained"}), "deliveries": ("attempts", 2),
                "access": ("reason", "no_session"), "usage": ("active_minutes", 7),
                "jobs": ("state", "awaiting"), "credentials": ("label", "Retained PIN")}
            field, value = fields[op]
            assert records[0][field] == value

    # Object routes conceal via scoped_adapter/binding; space routes via 481/494.
    prove(w.space, w.objects, key, lambda c: send(c or w.client, "devices:" + name, args, method, body),
          check, status=status, outsiders=[(w.foreign, foreign_refusal(native, space_path=op in {"list", "profile", "profile_set", "credentials", "credential_set"}))],
          audits={audit: 1} if audit else {},
          after_off=(403, "permission_denied") if native and op == "unbind" else None)
