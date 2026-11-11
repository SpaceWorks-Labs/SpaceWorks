"""Historical borrowers resolve through verified aliases; no contact matching."""
import pytest
from apps.accounts.loan_context_identity import borrower_aliases
from tests.test_request_workflow import make_user
from tests.data_export.test_merged_fields import _merge

pytestmark = pytest.mark.django_db


def test_shell_resolves_survivor_and_rejects_unrelated():
    shell, survivor, other = (make_user(name) for name in ("loan-shell", "loan-survivor", "loan-other"))
    _merge(shell, survivor)
    assert {shell.pk, survivor.pk} <= borrower_aliases(shell)
    assert other.pk not in borrower_aliases(shell)


def test_missing_and_cycle_fail_closed(monkeypatch):
    from apps.accounts.loan_context_identity import User
    class Query:
        def __init__(self, value): self.value = value
        def values_list(self, *args, **kwargs): return self
        def first(self): return self.value
    class Borrower: pk = 999001
    monkeypatch.setattr(User._base_manager, "filter", lambda **kwargs: Query(None))
    with pytest.raises(ValueError, match="Missing"):
        borrower_aliases(Borrower())
    monkeypatch.setattr(User._base_manager, "filter", lambda **kwargs: Query((Borrower.pk, Borrower.pk)))
    with pytest.raises(ValueError, match="Cyclic"):
        borrower_aliases(Borrower())
