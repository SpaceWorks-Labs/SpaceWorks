"""Decision 507: collection GET/POST; slot detail DELETE only, with typed 405s."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.events.certificates.signatory_models import EventCertificateSignatory
from tests.events.checkin_helpers import client_for, make_event, make_member, make_space, make_staff

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    space = make_space("cx2-signatories")
    space.enabled_features = [*space.enabled_features, "events.certificate_designer"]
    space.save(update_fields=["enabled_features"])
    event = make_event(space)
    staff = make_staff(space)
    url = reverse("events-programme-admin-certificate-signatory-detail", kwargs={"pk": event.pk, "slot": 1})
    return space, event, staff, url


def _collection(event):
    return reverse("events-programme-admin-certificate-signatories", kwargs={"pk": event.pk})


def _seed(event, staff):
    response = client_for(staff).post(_collection(event), {"slot": 1, "name": "Dr Ω", "title": "Director"}, format="json")
    assert response.status_code == 200, response.data
    return EventCertificateSignatory.objects.get(event=event, slot=1)


def test_collection_create_read_and_detail_delete_audit_each_change(world):
    space, event, staff, url = world
    client = client_for(staff)
    row = _seed(event, staff)
    response = client.get(_collection(event))
    assert response.status_code == 200
    assert response.data["signatories"][0]["id"] == row.pk
    response = client.delete(url)
    assert response.status_code == 200
    assert not EventCertificateSignatory.objects.filter(pk=row.pk).exists()
    assert list(AuditLog.objects.filter(makerspace=space, action__startswith="event.certificate_signatory_")
                .order_by("pk").values_list("action", flat=True)) == [
        "event.certificate_signatory_saved", "event.certificate_signatory_removed"]
    response = client.delete(url)
    assert (response.status_code, response.data["code"]) == (404, "not_found")
    assert AuditLog.objects.filter(makerspace=space, action="event.certificate_signatory_removed").count() == 1


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "x", "slot": 2}, {"name": "x", "unknown": True}, []])
def test_detail_post_is_405_for_every_body_and_writes_nothing(world, body):
    space, event, staff, url = world
    before = AuditLog.objects.filter(makerspace=space).count()
    response = client_for(staff).post(url, body, format="json")
    assert (response.status_code, response.data["code"]) == (405, "method_not_allowed")
    assert response["Allow"] == "DELETE"
    assert response.data["detail"]
    assert not EventCertificateSignatory.objects.filter(event=event).exists()
    assert AuditLog.objects.filter(makerspace=space).count() == before


@pytest.mark.parametrize("actor_kind,expected", [("member", (403, "permission_denied")),
                                                ("inventory_manager", (403, "permission_denied")),
                                                ("machine_manager", (403, "permission_denied")),
                                                ("booking_manager", (403, "permission_denied")),
                                                ("handover", (403, "permission_denied")),
                                                ("technician", (403, "permission_denied")),
                                                ("shop_manager", (403, "permission_denied")),
                                                ("fundraising", (403, "permission_denied")),
                                                ("other_tenant", (404, "not_found"))])
def test_detail_delete_enforces_role_and_tenant_before_writing(world, actor_kind, expected):
    space, event, staff, url = world
    row = _seed(event, staff)
    before = EventCertificateSignatory.objects.filter(pk=row.pk).values().get()
    audits = AuditLog.objects.count()
    from tests.fixed_roles.helpers import staff_account
    if actor_kind == "other_tenant":
        actor = make_staff(make_space("cx2-signatories-other"))
    elif actor_kind == "member":
        actor = make_member(space)
    else:
        actor = staff_account(space, "cx2-signatories-role", actor_kind)
    response = client_for(actor).delete(url)
    assert (response.status_code, response.data["code"]) == expected, response.data
    assert EventCertificateSignatory.objects.filter(pk=row.pk).values().get() == before
    assert AuditLog.objects.count() == audits


def test_event_manager_can_create_the_signatory_but_cannot_attach_another_tenants_member(world):
    space, event, staff, url = world
    from tests.fixed_roles.helpers import staff_account
    actor = staff_account(space, "cx2-signatory-event-manager", "event_manager")
    client = client_for(actor)
    foreign_member = make_member(make_space("cx2-signatory-foreign-member"))
    response = client.post(_collection(event), {"slot": 1, "name": "Director", "member_id": foreign_member.pk}, format="json")
    assert (response.status_code, response.data["member_id"].code) == (400, "invalid")
    assert response.json() == {"member_id": "Choose an active account of this space."}
    assert not EventCertificateSignatory.objects.filter(event=event).exists()
    response = client.post(_collection(event), {"slot": 1, "name": "Director"}, format="json")
    assert response.status_code == 200, response.data
    assert EventCertificateSignatory.objects.get(event=event, slot=1).name == "Director"
    assert client.delete(url).status_code == 200


@pytest.mark.parametrize("switch", ["events", "events.certificate_designer"])
def test_detail_off_on_preserves_the_signatory_and_refused_writes_are_inert(world, switch):
    space, event, staff, url = world
    client = client_for(staff)
    row = _seed(event, staff)
    before = EventCertificateSignatory.objects.filter(pk=row.pk).values().get()
    audits = AuditLog.objects.count()
    field = "enabled_features" if "." in switch else "enabled_modules"
    original = getattr(space, field)
    setattr(space, field, [key for key in original if key != switch])
    space.save(update_fields=[field])
    code = "feature_disabled" if "." in switch else "module_disabled"
    response = client.delete(url)
    assert (response.status_code, response.data["code"]) == (404, code), response.data
    assert response.data["feature" if "." in switch else "module"] == switch
    assert EventCertificateSignatory.objects.filter(pk=row.pk).values().get() == before
    assert AuditLog.objects.count() == audits
    setattr(space, field, original)
    space.save(update_fields=[field])
    response = client.get(_collection(event))
    assert response.status_code == 200
    assert response.data["signatories"][0]["id"] == row.pk
    assert client.delete(url).status_code == 200
    assert not EventCertificateSignatory.objects.filter(pk=row.pk).exists()


@pytest.mark.parametrize("method", ["get", "post", "patch", "put", "head", "options"])
@pytest.mark.parametrize("exists", [False, True])
@pytest.mark.parametrize("switch", [None, "events", "events.certificate_designer"])
def test_detail_unsupported_methods_are_405_with_delete_only_allow_and_no_writes(world, method, exists, switch):
    space, event, staff, url = world
    row = _seed(event, staff)
    if not exists:
        url = reverse("events-programme-admin-certificate-signatory-detail", kwargs={"pk": 987654, "slot": 1})
    if switch:
        field = "enabled_features" if "." in switch else "enabled_modules"
        setattr(space, field, [key for key in getattr(space, field) if key != switch])
        space.save(update_fields=[field])
    before = EventCertificateSignatory.objects.filter(pk=row.pk).values().get()
    audits = AuditLog.objects.count()
    response = getattr(client_for(staff), method)(url, {}, format="json")
    assert response.status_code == 405
    if method != "head":
        assert response.data["code"] == "method_not_allowed"
        assert response.data["detail"]
    assert response["Allow"] == "DELETE"
    assert EventCertificateSignatory.objects.filter(pk=row.pk).values().get() == before
    assert AuditLog.objects.count() == audits
