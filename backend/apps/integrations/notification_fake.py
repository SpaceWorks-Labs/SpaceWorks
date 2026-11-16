"""Deterministic fake, registered explicitly by tests, never by production startup."""
from .notification_providers import CallbackEvent, ProviderResult


class FakeProvider:
    def __init__(self, configuration=None):
        self.configuration = configuration
        self.calls = []
        self.results = []
        self.callback = None

    def send(self, delivery, rendered):
        self.calls.append((delivery.pk, rendered))
        return self.results.pop(0) if self.results else ProviderResult(True, f"fake-{delivery.pk}")

    def verify_callback(self, request) -> CallbackEvent | None:
        return self.callback

    def test(self, target):
        return ProviderResult(True, "fake-test")

    def start_challenge(self, challenge, code):
        return {"connect_url": f"https://example.invalid/connect?code={code}"}
