"""L13: public Google Sheet import source -- URL normalisation and the guarded fetch.

Every network call goes through an `httpx.MockTransport`; DNS is faked. No live network.
"""
import logging
import socket

import httpx
import pytest

from apps.admin_api import import_sources_sheets as sheets

SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd"
SHARE = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?usp=sharing#gid=42"
PUBLIC_IP, PRIVATE_IP = "142.250.70.14", "10.0.0.5"
CSV = b"Name,Email\r\nAsha,asha@example.test\r\nRavi,ravi@example.test\r\n"


@pytest.fixture
def dns(monkeypatch):
    table = {"docs.google.com": [PUBLIC_IP], "doc-0s-sheets.googleusercontent.com": ["142.250.70.33"]}

    def fake(host):
        if host not in table:
            raise socket.gaierror("no such host")
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))
                for ip in table[host]]

    monkeypatch.setattr(sheets, "_getaddrinfo", fake)
    return table


def _fetch(handler, url=SHARE, max_bytes=10_000, max_rows=100):
    return sheets.fetch_sheet(url, max_bytes=max_bytes, max_rows=max_rows, transport=httpx.MockTransport(handler))


def _code(excinfo):
    return excinfo.value.detail["code"]


@pytest.mark.parametrize("raw, expected", [
    (SHARE, f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=42"),
    (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}", f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"),
    (f"https://DOCS.google.com/spreadsheets/u/1/d/{SHEET_ID}/edit?gid=7",
     f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=7"),
    (f"  https://docs.google.com/spreadsheets/d/e/2PACX-{SHEET_ID}/pubhtml?gid=5&single=true ",
     f"https://docs.google.com/spreadsheets/d/e/2PACX-{SHEET_ID}/pub?output=csv&gid=5&single=true"),
])
def test_share_links_become_the_csv_export(raw, expected):
    assert sheets.export_url(raw) == expected


@pytest.mark.parametrize("raw", [
    "", "not a url", f"http://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
    f"https://docs.google.com.evil.test/spreadsheets/d/{SHEET_ID}", f"https://evil.test/docs.google.com/spreadsheets/d/{SHEET_ID}",
    f"https://user@docs.google.com/spreadsheets/d/{SHEET_ID}", f"https://docs.google.com:8443/spreadsheets/d/{SHEET_ID}",
    f"https://docs.google.com/document/d/{SHEET_ID}/edit", "https://docs.google.com/spreadsheets/d/short/edit",
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=1;DROP", f"https://docs.google.com/spreadsheets/d/{SHEET_ID} x",
    f"https://docs.google.com\\@evil.test/spreadsheets/d/{SHEET_ID}", "https://docs.google.com/spreadsheets/d/" + "a" * 3000,
])
def test_anything_else_is_sheet_url_invalid(raw):
    with pytest.raises(sheets.SheetImportError) as excinfo:
        sheets.export_url(raw)
    assert _code(excinfo) == "sheet_url_invalid" and excinfo.value.status_code == 400


def test_fetch_follows_google_redirect_pinned_without_cookies(dns):
    seen = []

    def handler(request):
        seen.append(request)
        if request.headers["host"] == "docs.google.com":
            return httpx.Response(307, headers={"location": "https://doc-0s-sheets.googleusercontent.com/export/x?y=1",
                                                "set-cookie": "NID=secret; Path=/; Domain=142.250.70.14"})
        return httpx.Response(200, headers={"content-type": "text/csv; charset=utf-8"}, content=CSV)

    fetched = _fetch(handler)
    assert fetched.content == CSV and len(fetched.sha256) == 64
    assert [request.url.host for request in seen] == [PUBLIC_IP, "142.250.70.33"]  # pinned to the checked address
    assert [request.headers["host"] for request in seen] == ["docs.google.com", "doc-0s-sheets.googleusercontent.com"]
    assert [request.extensions["sni_hostname"] for request in seen] == ["docs.google.com",
                                                                        "doc-0s-sheets.googleusercontent.com"]
    assert seen[0].url.path == f"/spreadsheets/d/{SHEET_ID}/export" and seen[0].url.params["gid"] == "42"
    assert all("cookie" not in request.headers and "authorization" not in request.headers for request in seen)
    assert fetched.response_fields() == {"source": "google_sheet", "sheet_sha256": fetched.sha256}


def test_cookies_set_by_google_are_never_sent_back(dns):
    seen = []

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(307, headers={"location": f"/spreadsheets/d/{SHEET_ID}/export?format=csv&again=1",
                                                "set-cookie": "NID=secret; Path=/"})
        return httpx.Response(200, headers={"content-type": "text/csv"}, content=CSV)

    assert _fetch(handler).content == CSV
    assert len(seen) == 2 and seen[1].headers["host"] == "docs.google.com" and "cookie" not in seen[1].headers


@pytest.mark.parametrize("location, code", [
    ("https://accounts.google.com/ServiceLogin?continue=x", "sheet_not_public"),
    ("https://evil.test/steal", "sheet_unreachable"),
    ("http://docs.google.com/spreadsheets/d/x/export", "sheet_unreachable"),
    ("https://doc-0s-sheets.googleusercontent.com:8443/x", "sheet_unreachable"),
])
def test_redirects_off_the_allow_list_are_never_followed(dns, location, code):
    seen = []

    def handler(request):
        seen.append(request.headers["host"])
        return httpx.Response(302, headers={"location": location})

    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(handler)
    assert _code(excinfo) == code and seen == ["docs.google.com"]


@pytest.mark.parametrize("answers", [[PRIVATE_IP], ["127.0.0.1"], ["169.254.169.254"], [PUBLIC_IP, "192.168.1.9"],
                                     ["::1"], ["::ffff:10.0.0.1"], ["fe80::1"]])
def test_private_loopback_and_link_local_addresses_are_refused(dns, answers):
    dns["docs.google.com"] = answers
    calls = []
    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(lambda request: calls.append(request) or httpx.Response(200, content=CSV))
    assert _code(excinfo) == "sheet_unreachable" and excinfo.value.status_code == 502 and not calls


def test_a_redirect_target_resolving_privately_is_refused(dns):
    dns["doc-0s-sheets.googleusercontent.com"] = [PRIVATE_IP]
    hosts = []

    def handler(request):
        hosts.append(request.headers["host"])
        return httpx.Response(307, headers={"location": "https://doc-0s-sheets.googleusercontent.com/export"})

    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(handler)
    assert _code(excinfo) == "sheet_unreachable" and hosts == ["docs.google.com"]


@pytest.mark.parametrize("error", [httpx.ConnectTimeout("slow"), httpx.ReadTimeout("slow"), httpx.ConnectError("down")])
def test_timeouts_and_transport_errors_are_sheet_unreachable(dns, error):
    def handler(request):
        raise error

    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(handler)
    assert _code(excinfo) == "sheet_unreachable" and excinfo.value.status_code == 502


def test_timeouts_are_configured_and_the_environment_is_ignored(dns, monkeypatch):
    captured = {}
    real = httpx.Client

    def spy(**kwargs):
        captured.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(httpx, "Client", spy)
    _fetch(lambda request: httpx.Response(200, headers={"content-type": "text/csv"}, content=CSV))
    timeout = captured["timeout"]
    assert timeout.connect == sheets.CONNECT_SECONDS and timeout.read == sheets.READ_SECONDS
    assert captured["follow_redirects"] is False and captured["trust_env"] is False


def test_unknown_host_is_unreachable(dns):
    dns.pop("docs.google.com")
    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(lambda request: httpx.Response(200, content=CSV))
    assert _code(excinfo) == "sheet_unreachable"


@pytest.mark.parametrize("response, code", [
    (httpx.Response(404), "sheet_not_public"), (httpx.Response(403), "sheet_not_public"),
    (httpx.Response(401), "sheet_not_public"), (httpx.Response(500), "sheet_unreachable"),
    (httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=b"<html>Sign in</html>"),
     "sheet_not_public"),
])
def test_status_and_html_pages(dns, response, code):
    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(lambda request: response)
    assert _code(excinfo) == code


def test_size_cap_streamed_and_declared(dns):
    big = b"Name,Email\r\n" + b"x,y@example.test\r\n" * 100
    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(lambda request: httpx.Response(200, headers={"content-type": "text/csv"}, content=big), max_bytes=200)
    assert _code(excinfo) == "sheet_too_large"
    declared = httpx.Response(200, headers={"content-type": "text/csv", "content-length": "999999"}, content=b"a")
    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(lambda request: declared, max_bytes=200)
    assert _code(excinfo) == "sheet_too_large"


def test_row_cap_counts_records_after_the_header(dns):
    body = b"Name,Email\r\n" + b"".join(f"P{n},p{n}@example.test\r\n".encode() for n in range(3)) + b",\r\n\r\n"
    ok = _fetch(lambda request: httpx.Response(200, headers={"content-type": "text/csv"}, content=body), max_rows=3)
    assert ok.content == body
    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(lambda request: httpx.Response(200, headers={"content-type": "text/csv"}, content=body), max_rows=2)
    assert _code(excinfo) == "sheet_too_large"


def test_redirect_loops_stop(dns):
    def handler(request):
        return httpx.Response(302, headers={"location": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export"})

    with pytest.raises(sheets.SheetImportError) as excinfo:
        _fetch(handler)
    assert _code(excinfo) == "sheet_unreachable"


def test_failure_logs_never_carry_the_link(dns, caplog):
    caplog.set_level(logging.WARNING, logger=sheets.__name__)
    with pytest.raises(sheets.SheetImportError):
        _fetch(lambda request: httpx.Response(404))
    record = next(item for item in caplog.records if item.getMessage() == "sheet_import_fetch_failed")
    assert record.code == "sheet_not_public" and record.reason == "status"
    assert SHEET_ID not in " ".join(str(value) for value in vars(record).values())
