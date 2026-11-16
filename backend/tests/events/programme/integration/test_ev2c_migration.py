"""Populated JSON conversion/custody backfill and fail-closed permanent receipt downgrade."""
from datetime import timedelta
from uuid import uuid4
import json

import pytest
from django.db import connection, DatabaseError
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)


def test_populated_upgrade_preserves_private_documents_and_backfills_permanent_custody():
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    before = [("events", "0045_g2b_subject_lifecycle")]
    after = [("events", "0046_g2c_private_assets")]
    executor.migrate(before)
    try:
        old = MigrationExecutor(connection).loader.project_state(before).apps
        # Only events is rolled back; makerspaces stays at its leaf (0105 dropped a column
        # the historical state still lists), so create the tenant with the live model.
        from apps.makerspaces.models import Makerspace
        space = Makerspace.objects.create(name="Custody upgrade", slug="ev2c-upgrade")
        old.get_model("encryption", "PiiMakerspaceWriteFence").objects.get_or_create(makerspace_id=space.pk)
        from apps.accounts.models import User
        user = User.objects.create(username="ev2c-upgrade", account_kind="member")
        event = old.get_model("events", "Event").objects.create(makerspace_id=space.pk, title="Custody upgrade",
            starts_at=timezone.now(), ends_at=timezone.now()+timedelta(hours=1))
        team = old.get_model("events", "HackathonTeam").objects.create(event_id=event.pk, leader_id=user.pk,
            name="Historical makers", state="disbanded")
        project = old.get_model("events", "HackathonSubmission").objects.create(event_id=event.pk, team_id=team.pk,
            form_answers={"emergency": {"name": "Private upgrade contact"}})
        ident = uuid4()
        asset = old.get_model("events", "HackathonParticipantAsset").objects.create(event_id=event.pk,
            member_id=user.pk, uploaded_by_id=user.pk, public_id=ident, kind="resume", extension="pdf", subtype="pdf",
            original_filename="resume.pdf", declared_mime="application/pdf", declared_bytes=8, effective_cap=10,
            reserved_bytes=8, object_key=f"final/{ident}", staging_key=f"staging/{ident}", verification_key=f"verification/{ident}")
        MigrationExecutor(connection).migrate(after)
        current = MigrationExecutor(connection).loader.project_state(after).apps
        converted = current.get_model("events", "HackathonSubmission").objects.get(pk=project.pk)
        assert json.loads(converted.form_answers) == {"emergency": {"name": "Private upgrade contact"}}
        receipt = current.get_model("events", "EventAssetObligation").objects.get(asset_uuid=ident)
        assert receipt.asset_id_snapshot == asset.pk and receipt.reserved_bytes == 8
        assert (receipt.object_key, receipt.staging_key, receipt.verification_key) == (
            asset.object_key, asset.staging_key, asset.verification_key)
        with pytest.raises(DatabaseError, match="Permanent asset obligations"):
            MigrationExecutor(connection).migrate(before)
    finally:
        MigrationExecutor(connection).migrate(latest)
