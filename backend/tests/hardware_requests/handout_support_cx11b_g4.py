"""Eligible physical borrower with real presence and uploaded-evidence storage port."""
from apps.accounts.models import User
from apps.evidence.storage import EvidenceValidationResult
from tests.accounts.account_factories import make_membership
from tests.modules.switch_matrix_object_helpers import object_world
from tests.p3_fixbe_helpers import staff_presence
from tests.return_helpers import make_issue_evidence, make_product, make_return_evidence


def handout_world(native, monkeypatch):
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    make_membership(actor, space)
    staff_presence(actor, space)
    product = make_product(space, public_self_checkout_enabled=True)
    issue = make_issue_evidence(space, actor)
    returned = make_return_evidence(space, actor)
    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
        lambda photo, limit: EvidenceValidationResult(size=77, content_type="image/png"))
    return space, client, actor, product, issue, returned
