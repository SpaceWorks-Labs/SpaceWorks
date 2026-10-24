"""Explicit E model import list for G's models_programme barrel; no migrations."""
from apps.events.credentials.models import EventRegistrationCredential, EventCredentialCommand
from apps.events.profile_photos.models import EventMemberPresentation, EventMemberCard, EventPresentationCommand
from .models import EventCertificatePublicationPolicy, CertificateIssueBatch, CertificateIssueBatchItem
from .library_models import (EventCertificateLibraryTemplate, EventCertificateLibraryRevision,
                             EventCertificateLibraryArtwork, EventCertificateLibraryCommand)
from .print_models import EventBadgeTemplateRevision, BadgePrintJob, BadgePrintResource

__all__ = [
    "EventRegistrationCredential", "EventCredentialCommand", "EventMemberPresentation", "EventMemberCard",
    "EventPresentationCommand", "EventCertificatePublicationPolicy", "CertificateIssueBatch",
    "CertificateIssueBatchItem", "EventCertificateLibraryTemplate", "EventCertificateLibraryRevision",
    "EventCertificateLibraryArtwork", "EventCertificateLibraryCommand", "EventBadgeTemplateRevision",
    "BadgePrintJob", "BadgePrintResource",
]
