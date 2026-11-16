"""The optional reimbursement module uses SurfaceOff before parsing or mutating commands."""
import pytest

from apps.audit.models import AuditLog
from apps.event_reimbursements.config_models import ReimbursementProgramme
from apps.event_reimbursements.views_admin import ProgrammeView
from tests.accounts.test_reauthentication import request as session_request
from tests.event_reimbursements.test_privacy import call

pytestmark = pytest.mark.django_db(transaction=True)


def test_reimbursement_routes_refuse_off_and_restore_retained_programme(world):
    def probe(method):
        req = session_request(world.manager)
        req.method = method
        return call(ProgrammeView, req, pk=world.event.pk)
    response = probe("GET")
    assert response.status_code == 200, response.data
    before = ReimbursementProgramme.objects.filter(pk=world.programme.pk).values().get()
    original = world.space.enabled_modules
    world.space.enabled_modules = [key for key in original if key != "event_reimbursements"]
    world.space.save(update_fields=["enabled_modules"])
    audit_count = AuditLog.objects.count()
    for method in ("GET", "POST", "PATCH"):
        response = probe(method)
        assert (response.status_code, response.data["code"], response.data["module"]) == (
            404, "module_disabled", "event_reimbursements")
        assert ReimbursementProgramme.objects.filter(pk=world.programme.pk).values().get() == before
    assert AuditLog.objects.count() == audit_count
    world.space.enabled_modules = original
    world.space.save(update_fields=["enabled_modules"])
    response = probe("GET")
    assert response.status_code == 200, response.data
    assert ReimbursementProgramme.objects.filter(pk=world.programme.pk).values().get() == before
