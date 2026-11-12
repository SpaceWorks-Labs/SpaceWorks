"""SECFIX-A: the shared outbound address policy and the bounded, pinned transport (security review M1, lead 2).

The transport tests talk to a real socket server on 127.0.0.1 (a pinned ``Target`` is built directly, since the
policy refuses loopback): a normal answer, an oversized body, a slow drip, a redirect, and DNS never consulted
while sending.
"""
import socket
import threading
import time
from ipaddress import ip_network

import pytest

from apps import outbound_http, outbound_policy
from apps.outbound_policy import OutboundRefused, PinnedAddress, Target, refusal, resolve


def _answers(*ips, port=443):
    return lambda *a, **k: [((socket.AF_INET6 if ":" in ip else socket.AF_INET), 1, 6, "", (ip, port))
                            for ip in ips]


# --- address policy ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("address", [
    "169.254.169.254", "100.100.100.200", "127.0.0.1", "0.0.0.0", "224.0.0.1", "240.0.0.1", "fe80::1", "::1",
    "fd00:ec2::254", "::ffff:169.254.169.254", "64:ff9b::a9fe:a9fe", "2002:a9fe:a9fe::1",
])
def test_metadata_loopback_and_embedded_forms_are_always_refused(address):
    assert refusal(address, allow_private=True) == "blocked_address"


@pytest.mark.parametrize("address", ["10.0.0.5", "192.168.1.20", "172.18.0.2", "100.64.1.1", "fc00::1"])
def test_private_and_cgnat_need_an_explicit_allowance(address):
    assert refusal(address) == "private_address"
    assert refusal(address, allow_private=True) is None


def test_public_addresses_pass_and_extra_networks_are_refused():
    assert refusal("93.184.216.34") is None and refusal("2606:4700::1") is None
    assert refusal("172.18.0.9", allow_private=True, extra_blocked=(ip_network("172.18.0.0/16"),)) == "blocked_address"


def test_loopback_only_with_the_platform_allowance():
    assert refusal("127.0.0.1", allow_private=True, allow_loopback=True) is None
    assert refusal("169.254.169.254", allow_private=True, allow_loopback=True) == "blocked_address"


def test_one_bad_answer_refuses_the_whole_name(monkeypatch):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _answers("93.184.216.34", "10.0.0.1"))
    with pytest.raises(OutboundRefused) as caught:
        resolve("https://mixed.example")
    assert caught.value.reason == "private_address"


def test_resolve_pins_every_answer_and_keeps_host_and_path(monkeypatch):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _answers("93.184.216.34", port=8443))
    target = resolve("https://hooks.example:8443/p?q=1", ports={443, 8443})
    assert target.host_header == "hooks.example:8443" and target.request_target == "/p?q=1"
    assert [a.ip for a in target.addresses] == ["93.184.216.34"]


@pytest.mark.parametrize("url,reason", [
    ("http://hooks.example/", "invalid_url"), ("https://u:p@hooks.example/", "invalid_url"),
    ("https://hooks.example/#x", "invalid_url"), ("https://hooks.example:22/", "port_not_allowed"),
])
def test_malformed_or_wrong_port_is_refused_before_dns(monkeypatch, url, reason):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", lambda *a, **k: pytest.fail("no DNS"))
    with pytest.raises(OutboundRefused) as caught:
        resolve(url, ports={443, 8443})
    assert caught.value.reason == reason


# --- transport against a real local server ----------------------------------------------------------------------
class _Server:
    def __init__(self, reply):
        self.reply, self.requests = reply, []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.stop = threading.Event()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(5)
                data = b""
                while b"\r\n\r\n" not in data:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                self.requests.append(data)
                try:
                    self.reply(conn)
                except OSError:
                    pass

    def target(self, path="/"):
        return Target("http", "player.example", self.port, f"player.example:{self.port}", path,
                      (PinnedAddress(socket.AF_INET, ("127.0.0.1", self.port)),))

    def close(self):
        self.stop.set()
        self.sock.close()


@pytest.fixture
def server():
    made = []

    def make(reply):
        made.append(_Server(reply))
        return made[-1]
    yield make
    for item in made:
        item.close()


def _send(conn, status=200, body=b"{}", extra=b""):
    conn.sendall(b"HTTP/1.1 %d X\r\nContent-Length: %d\r\n%s\r\n" % (status, len(body), extra) + body)


def test_a_normal_answer_is_read_with_the_original_host_header(server, monkeypatch):
    srv = server(lambda conn: _send(conn, body=b'{"ok": true}'))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("the transport never resolves"))
    response = outbound_http.send(srv.target("/api/v2/info"), "GET", headers={"Accept": "application/json"},
                                  max_bytes=1024, deadline=5)
    assert response.status == 200 and response.body == b'{"ok": true}'
    assert b"GET /api/v2/info HTTP/1.1" in srv.requests[0]
    assert f"Host: player.example:{srv.port}".encode() in srv.requests[0]


def test_an_oversized_body_stops_at_the_cap(server):
    srv = server(lambda conn: _send(conn, body=b"x" * 50_000))
    with pytest.raises(outbound_http.OutboundError) as caught:
        outbound_http.send(srv.target(), "GET", max_bytes=1024, deadline=5)
    assert caught.value.reason == "too_large"
    assert outbound_http.send(srv.target(), "GET", max_bytes=1024, deadline=5, truncate=True).status == 200


def test_a_slow_drip_is_cut_at_the_overall_deadline(server):
    def drip(conn):
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 100000\r\n\r\n")
        for _ in range(200):  # one byte every 0.1 s: never idle long enough for the read timeout
            conn.sendall(b"x")
            time.sleep(0.1)
    srv = server(drip)
    started = time.monotonic()
    with pytest.raises(outbound_http.OutboundError) as caught:
        outbound_http.send(srv.target(), "GET", max_bytes=1_000_000, read_timeout=5, deadline=1)
    assert caught.value.reason == "timeout" and time.monotonic() - started < 4


def test_a_dripping_header_is_cut_at_the_overall_deadline(server):
    def drip(conn):
        for _ in range(200):
            conn.sendall(b"X")
            time.sleep(0.1)
    srv = server(drip)
    started = time.monotonic()
    with pytest.raises(outbound_http.OutboundError) as caught:
        outbound_http.send(srv.target(), "GET", max_bytes=1024, read_timeout=5, deadline=1)
    assert caught.value.reason in ("timeout", "unreachable") and time.monotonic() - started < 4


def test_a_redirect_is_returned_never_followed(server):
    srv = server(lambda conn: _send(conn, status=302, body=b"", extra=b"Location: http://169.254.169.254/\r\n"))
    response = outbound_http.send(srv.target(), "GET", max_bytes=1024, deadline=5)
    assert response.status == 302 and len(srv.requests) == 1


def test_a_closed_port_is_unreachable():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    target = Target("http", "x.example", port, "x.example", "/", (PinnedAddress(socket.AF_INET, ("127.0.0.1", port)),))
    with pytest.raises(outbound_http.OutboundError) as caught:
        outbound_http.send(target, "GET", max_bytes=10, deadline=3)
    assert caught.value.reason in ("unreachable", "timeout")
