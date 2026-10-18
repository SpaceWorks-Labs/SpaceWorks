"""Explicit B model barrel for G's models_programme imports, with no app hook."""
from .models_assets import SubmissionAsset, HackathonParticipantAsset, EventAssetUsage, SubmissionAssetWork
from .models_projects import (
    HackathonSubmission, SubmissionSnapshot, SubmissionLink, SnapshotAsset, SnapshotLink,
    SnapshotTrack, SnapshotPrize, SubmissionIntegrityFlag,
)

__all__ = ["SubmissionAsset", "HackathonParticipantAsset", "EventAssetUsage", "SubmissionAssetWork",
           "HackathonSubmission", "SubmissionSnapshot", "SubmissionLink", "SnapshotAsset", "SnapshotLink",
           "SnapshotTrack", "SnapshotPrize", "SubmissionIntegrityFlag"]
