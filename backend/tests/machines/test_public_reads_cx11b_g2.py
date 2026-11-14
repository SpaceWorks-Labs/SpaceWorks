"""Public catalogue and bearer reads use their public contract, never invented staff standing."""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.machines.models import MachineConsumablePool, MachineType, ServiceQueue
from apps.machines.models_materials import MachineMaterial
from tests.machines.eta_helpers import job
from tests.machines.member_support_cx11b_g2 import member_world
from tests.machines.route_support_cx11b_g2 import command, no_domain_writes, prove, response_pair, rows

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]
CASES = [("public-machines", "machines", "module_disabled"),
         ("public-machine-details", "machines", "module_disabled"),
         ("public-machine-details", "machines.public_detail", "feature_disabled"),
         ("public-machine-detail", "machines", "module_disabled"),
         ("public-machine-detail", "machines.public_detail", "feature_disabled"),
         ("public-machine-job-types", "machine_service", "module_disabled"),
         ("public-machine-job-types", "machines.job_requests", "feature_disabled"),
         ("public-machine-job-types", "membership", "machine_intake_unavailable"),
         ("public-machine-job-types", "presence", "machine_intake_unavailable"),
         ("public-machine-intake", "machines", "module_disabled"),
         ("public-machine-intake", "machine_service", "module_disabled"),
         ("public-machine-intake", "machines.material_catalogue", "policy"),
         ("public-machine-intake", "machines.structured_intake", "policy"),
         ("public-printer-service-queues", "machine_service", "module_disabled"),
         ("public-printer-service-queues", "machines.job_requests", "feature_disabled"),
         ("public-printer-service-pools", "machine_service", "module_disabled"),
         ("public-printer-service-pools", "machines.job_requests", "feature_disabled"),
         ("public-printer-service-status", "machine_service", "module_disabled"),
         ("public-machine-service-status", "machine_service", "module_disabled")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,key,code", CASES)
def test_public_reads_contain_the_seed_and_restore_under_their_actual_contract(native, name, key, code):
    w = member_world(native)
    # Anonymous callers are expressly admitted on public catalogue and bearer reads
    # (494/486 person/public distinction, 520 never turns a bearer read into staff RBAC).
    w.foreign = APIClient()
    printer_type = MachineType.objects.get(makerspace__isnull=True, slug="3d_printer")
    queue = ServiceQueue.objects.create(makerspace=w.space, machine_type=printer_type, name="G2 printer queue")
    pool = MachineConsumablePool.objects.create(makerspace=w.space, machine_type=printer_type, material="PLA",
        color="Blue", remaining_grams=90, initial_grams=100, is_public=True, is_active=True)
    material = MachineMaterial.objects.create(makerspace=w.space, machine_type=w.machine_type,
                                              name="Retained birch", colours=["Natural"])
    schema = {"version": 1, "fields": [{"key": "depth", "label": "Depth", "type": "text", "required": False}]}
    if name == "public-machine-intake":
        w.machine_type.intake_schema = schema
        w.machine_type.save(update_fields=["intake_schema"])
    args = [w.space.slug]
    if name == "public-machine-detail":
        args.append(w.machine.pk)
    if name == "public-machine-intake":
        args.append(w.machine_type.pk)
    if name.endswith("status"):
        if name.startswith("public-printer"):
            w.queue = queue
        if name.startswith("public-printer"):
            MachineMaterial.objects.create(makerspace=w.space, machine_type=printer_type,
                                           name="PLA", colours=["Blue"])
            from apps.machines.service_workflow import submit
            request = submit(w.queue, w.member, member=w.member, actor=w.member,
                requester_name="G2 printer owner", contact_email=w.member.email, contact_phone="",
                title="Retained bearer job", capability_payload={
                    "requested_material": "PLA", "requested_color": "Blue", "quantity": 1})
        else:
            request = job(w, member=w.member, title="Retained bearer job")
        args = [request.public_token]

    def check(response):
        if name == "public-machine-intake":
            assert response.data == {"materials": [{"id": material.pk, "name": "Retained birch", "colours": ["Natural"]}],
                                     "intake_schema": schema}
        elif name == "public-machine-job-types":
            assert [(r["queue_id"], r["name"], r["machine_type_id"]) for r in response.data if r["queue_id"] == w.queue.pk] == [
                (w.queue.pk, "Retained job queue", w.kind.pk)]
        elif name.endswith("queues"):
            assert [(r["id"], r["name"], r["machine_type_id"]) for r in response.data] == [(queue.pk, "G2 printer queue", printer_type.pk)]
        elif name.endswith("pools"):
            assert response.data == [{"id": pool.pk, "material": "PLA", "color": "Blue"}]
        elif name.endswith("status"):
            assert (str(response.data["public_token"]), response.data["title"], response.data["status"]) == (
                str(request.public_token), "Retained bearer job", "pending")
            assert set(response.data).isdisjoint({"contact_email", "contact_phone", "requester_name", "member_id"})
        else:
            data = [response.data] if name == "public-machine-detail" else rows(response)
            assert [r["name"] for r in data] == ["Retained machine"]
            if name != "public-machines":
                assert [r["id"] for r in data] == [w.machine.pk]

    def policy(response):
        expected = {"materials": [] if key.endswith("material_catalogue") else [
            {"id": material.pk, "name": "Retained birch", "colours": ["Natural"]}],
            "intake_schema": {} if key.endswith("structured_intake") else schema}
        assert response.data == expected

    off = (200, None) if code == "policy" else (404, code)
    prove(w, key, lambda c: command(c, name, "get", args), check, off=off, off_check=policy if code == "policy" else None,
          foreign=(200, None), foreign_check=check, foreign_off=off,
          foreign_off_check=policy if code == "policy" else None)
    if name.endswith("status"):
        with no_domain_writes():
            missing = command(APIClient(), name, "get", [uuid.UUID(int=1)])
        assert response_pair(missing) == (404, "not_found")
