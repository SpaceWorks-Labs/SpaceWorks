"""Small, bounded transport for installer diagnostics; errors never contain payloads."""
import json
import urllib.error
import urllib.request


class ProbeError(Exception):
    def __init__(self, code):
        self.code = code


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, *, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=10) as response:
            return response.status, response.read(65537)
    except urllib.error.HTTPError as error:
        return error.code, b""


def json_get(url):
    status, body = request(url)
    if status != 200 or len(body) > 65536:
        raise ProbeError("http_health_failed")
    return json.loads(body)
