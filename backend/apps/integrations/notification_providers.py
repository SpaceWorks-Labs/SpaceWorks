"""Frozen provider seam. Adapters verify signatures before returning callback events."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderResult:
    accepted: bool
    provider_id: str = ""
    retryable: bool = False
    error_code: str = ""
    sanitized_error: str = ""
    ambiguous: bool = False
    retry_after: int | None = None


@dataclass(frozen=True)
class EndpointProof:
    code: str
    destination: str
    integration_identity: str
    # Telegram private chat/from.id, OAuth workspace/subject, or inbound WA sender.
    subject: str
    private: bool = False


@dataclass(frozen=True)
class CallbackEvent:
    provider_id: str = ""
    state: str = ""
    proof: EndpointProof | None = None
    endpoint_id: int | None = None
    opt_out: bool = False
    inbound: bool = False
    delivery_id: int | None = None
    delivery_attempt: int | None = None
    identity_digest: str = ""
    opt_in: bool = False
    provider_timestamp: str | None = None


class Provider(Protocol):
    def send(self, delivery, rendered: dict) -> ProviderResult: ...
    def send_document(self, delivery, *, filename, pdf_bytes, caption) -> ProviderResult: ...
    def verify_callback(self, request) -> CallbackEvent | None: ...
    def test(self, target) -> ProviderResult: ...


class ProofProvider(Provider, Protocol):
    def start_challenge(self, challenge, code: str) -> dict:
        """Return {connect_url?, instructions?}; send WA opt-in challenge if needed."""
        ...


PROVIDERS = {}


def register_provider(channel, provider, factory):
    """AppConfig.ready registers factories; no credentials or database work at import."""
    key = (channel, provider)
    if key in PROVIDERS and PROVIDERS[key] is not factory:
        raise ValueError("Duplicate notification provider")
    PROVIDERS[key] = factory


def provider_for(configuration):
    factory = PROVIDERS.get((configuration.channel, configuration.provider))
    return factory(configuration) if factory else None


def safe_error(result):
    if isinstance(result.error_code, str) and result.error_code.isascii() and result.error_code.isdigit() and len(result.error_code) <= 16:
        return result.error_code
    # Provider text can contain destination ids, tokens or echoed message bodies.
    # Persist only a fixed code; sanitized_error is for typed adapter diagnostics.
    allowed = {"timeout", "rate_limited", "unavailable", "blocked", "invalid_endpoint",
               "template_required", "not_configured", "provider_error", "quota_exceeded", "unsupported",
               "document_render_failed", "document_size_exceeded", "document_not_authorized",
               "ambiguous_timeout", "connection_failed", "invalid_response", "attempts_exhausted"}
    return result.error_code if result.error_code in allowed else "provider_error"
