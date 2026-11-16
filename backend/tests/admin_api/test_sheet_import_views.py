"""L13: the member import and the ID-programme import accept a public Google Sheet.

The sheet's CSV goes through the same preview/de-dup/apply as an upload (#128 C-13), behind
`membership.import_sheets` / `membership.id_programmes_import_sheets` (off = 404).
Network and DNS are mocked.
"""
import functools
import socket

import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.admin_api import import_sources_sheets as sheets
from apps.audit.models import AuditLog
from apps.id_programmes.models import IdProgrammeCard
from apps.makerspaces.models import ImportedMember, MembershipImportBatch, MembershipRequest
from tests.admin_api.test_member_import import CSV as MEMBER_CSV
from tests.makerspaces.l4_helpers import features_on, plan, space_with_manager
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db
SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=0"


@pytest.fixture
def google(monkeypatch, settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
    state = {"body": MEMBER_CSV.encode(), "calls": 0}

    def handler(request):
        state["calls"] += 1
        return httpx.Response(200, headers={"content-type": "text/csv"}, content=state["body"])

    monkeypatch.setattr(sheets, "_getaddrinfo",
                        lambda host: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.70.14", 443))])
    monkeypatch.setattr(sheets, "fetch_sheet",
                        functools.partial(sheets.fetch_sheet, transport=httpx.MockTransport(handler)))
    return state


def _member_space(slug, *keys):
    space, manager = space_with_manager(slug)
    features_on(space, *keys)
    plan(space, "Monthly")
    return space, authenticated_client(manager)


def _sheet(**extra):
    return {"source": "google_sheet", "url": URL, **extra}


def test_member_preview_from_a_sheet_matches_the_csv_preview(google):
    space, client = _member_space("sheet-preview", "import", "import_sheets")
    sheet = client.post(reverse("admin-member-import-preview", args=[space.pk]), _sheet(), format="multipart")
    assert sheet.status_code == 200, sheet.content
    upload = SimpleUploadedFile("m.csv", MEMBER_CSV.encode(), content_type="text/csv")
    csv = client.post(reverse("admin-member-import-preview", args=[space.pk]), {"file": upload}, format="multipart")
    body = sheet.json()
    assert body["source"] == "google_sheet" and len(body["sheet_sha256"]) == 64
    assert {key: body[key] for key in ("counts", "rows", "mapping", "total_rows")} == \
        {key: csv.json()[key] for key in ("counts", "rows", "mapping", "total_rows")}
    assert not ImportedMember.objects.exists() and not MembershipRequest.objects.exists()


def test_member_sheet_source_is_404_while_its_switch_is_off(google):
    space, client = _member_space("sheet-off", "import")
    response = client.post(reverse("admin-member-import-preview", args=[space.pk]), _sheet(), format="multipart")
    assert response.status_code == 404 and google["calls"] == 0
    upload = SimpleUploadedFile("m.csv", MEMBER_CSV.encode(), content_type="text/csv")
    assert client.post(reverse("admin-member-import-preview", args=[space.pk]), {"file": upload},
                       format="multipart").status_code == 200
    assert client.post(reverse("admin-member-import-preview", args=[space.pk]), {},
                       format="multipart").status_code == 400


def test_member_apply_from_a_sheet_invites_and_audits_the_source(google):
    space, client = _member_space("sheet-apply", "import", "import_sheets")
    preview = client.post(reverse("admin-member-import-preview", args=[space.pk]), _sheet(), format="multipart").json()
    response = client.post(reverse("admin-member-import-apply", args=[space.pk]),
                           _sheet(sheet_sha256=preview["sheet_sha256"], record_only_rows="[6]"), format="multipart")
    assert response.status_code == 200, response.content
    assert response.json()["counts"]["invited"] == 1 and response.json()["counts"]["record_only"] == 1
    asha = ImportedMember.objects.get(external_number="OLD-1")
    assert asha.status == "invited" and asha.invitation.user_id is None  # never linked (C-13)
    batch = MembershipImportBatch.objects.get()
    assert batch.file_name == "Google Sheet" and batch.file_kind == "csv"
    entry = AuditLog.objects.get(action="membership.imported")
    assert entry.meta["source"] == "google_sheet" and SHEET_ID not in str(entry.meta)


def test_member_apply_refuses_a_sheet_changed_since_the_preview(google):
    space, client = _member_space("sheet-changed", "import", "import_sheets")
    preview = client.post(reverse("admin-member-import-preview", args=[space.pk]), _sheet(), format="multipart").json()
    google["body"] = (MEMBER_CSV + "Late,late@example.test,,,,,,\n").encode()
    response = client.post(reverse("admin-member-import-apply", args=[space.pk]),
                           _sheet(sheet_sha256=preview["sheet_sha256"]), format="multipart")
    assert response.status_code == 400 and response.json()["code"] == "sheet_changed"
    assert not ImportedMember.objects.exists() and not AuditLog.objects.filter(action="membership.imported").exists()


def test_member_file_import_audits_source_file(google):
    space, client = _member_space("sheet-file", "import")
    upload = SimpleUploadedFile("m.csv", MEMBER_CSV.encode(), content_type="text/csv")
    assert client.post(reverse("admin-member-import-apply", args=[space.pk]), {"file": upload},
                       format="multipart").status_code == 200
    assert AuditLog.objects.get(action="membership.imported").meta["source"] == "file"


@pytest.mark.parametrize("url, code", [("https://example.test/sheet.csv", "sheet_url_invalid"), ("", "sheet_url_invalid")])
def test_member_sheet_errors_are_typed(google, url, code):
    space, client = _member_space(f"sheet-err-{len(url)}", "import", "import_sheets")
    response = client.post(reverse("admin-member-import-preview", args=[space.pk]),
                           {"source": "google_sheet", "url": url}, format="multipart")
    assert response.status_code == 400 and response.json()["code"] == code and google["calls"] == 0


def _programme(slug, *features):
    from apps.id_programmes import services
    from apps.organizations.models import Organization, OrganizationMakerspace
    from tests.l3_local.helpers import card_space, manager
    space = card_space(slug, features=("membership.id_programmes", *features))
    org = Organization.objects.create(name=f"Org {slug}", slug=f"org-{slug}")
    OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="owner")
    sm = manager(space)
    return sm, services.create(sm, org, space, {"name": "Student ID"})


def test_programme_import_from_a_sheet(google):
    sm, programme = _programme("sheet-ip", "membership.id_programmes_import_sheets")
    google["body"] = b"Full Name,Email\r\nPriya,priya@example.com\r\nDup,priya@example.com\r\n"
    client = authenticated_client(sm)
    preview = client.post(f"/api/v1/admin/id-programmes/{programme.pk}/imports/preview", _sheet(), format="json")
    assert preview.status_code == 200, preview.content
    body = preview.json()
    assert body["to_create"] == 1 and body["mapping"] == {"name": 0, "email": 1} and body["source"] == "google_sheet"
    commit = client.post(f"/api/v1/admin/id-programmes/{programme.pk}/imports",
                         _sheet(mapping=body["mapping"], sheet_sha256=body["sheet_sha256"]), format="json")
    assert commit.status_code == 200, commit.content
    assert commit.json()["created"] == 1
    card = IdProgrammeCard.objects.get(programme=programme)
    assert card.source == "import" and card.user_id is None and card.status == "pending"
    entry = AuditLog.objects.get(action="id_programme.cards_imported")
    assert entry.meta["source"] == "google_sheet" and SHEET_ID not in str(entry.meta)


def test_programme_sheet_source_is_404_while_its_switch_is_off(google):
    sm, programme = _programme("sheet-ip-off")
    client = authenticated_client(sm)
    response = client.post(f"/api/v1/admin/id-programmes/{programme.pk}/imports/preview", _sheet(), format="json")
    assert response.status_code == 404 and google["calls"] == 0
    pasted = client.post(f"/api/v1/admin/id-programmes/{programme.pk}/imports/preview",
                         {"content": "Name,Email\r\nA,a@example.com\r\n"}, format="json")
    assert pasted.status_code == 200 and "source" not in pasted.json()


def test_programme_sheet_over_the_row_cap_is_too_large(google, monkeypatch):
    from apps.id_programmes import imports
    monkeypatch.setattr(imports, "MAX_ROWS", 1)
    sm, programme = _programme("sheet-ip-big", "membership.id_programmes_import_sheets")
    google["body"] = b"Name,Email\r\nA,a@example.com\r\nB,b@example.com\r\n"
    response = authenticated_client(sm).post(f"/api/v1/admin/id-programmes/{programme.pk}/imports/preview",
                                             _sheet(), format="json")
    assert response.status_code == 400 and response.json()["code"] == "sheet_too_large"


def test_capabilities_need_their_parent_import():
    from apps.makerspaces.capabilities import FEATURES
    assert FEATURES["membership.import_sheets"].requires_features == ("membership.import",)
    assert FEATURES["membership.id_programmes_import_sheets"].requires_features == ("membership.id_programmes",)
    assert not FEATURES["membership.import_sheets"].default_enabled
    assert not FEATURES["membership.id_programmes_import_sheets"].default_enabled
