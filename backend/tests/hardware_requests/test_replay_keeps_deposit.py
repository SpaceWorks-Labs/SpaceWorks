"""Payments audit 0.12.0 A-4: the deposit raised before a refusal survives the replay's rollback."""

from types import SimpleNamespace

from apps.hardware_requests import replay_execute


def test_deposit_refusal_re_raises_the_deposit_outside_the_rolled_back_transaction(monkeypatch):
    calls = []
    request = SimpleNamespace(pk=7)

    class _Qs:
        def select_related(self, *_):
            return self

        def get(self, pk):
            assert pk == 7
            return request

    monkeypatch.setattr("apps.hardware_requests.models.HardwareRequest.objects", _Qs())
    monkeypatch.setattr("apps.hardware_requests.loan_charges_issue.deposit_quote", lambda r: "quote")
    monkeypatch.setattr("apps.hardware_requests.loan_charges_issue._deposit",
                        lambda r, user, priced: calls.append((r, user, priced)))
    exc = SimpleNamespace(payment=SimpleNamespace(pk=1, subject_id=7))
    replay_execute.keep_raised_deposit(exc, "staff")
    assert calls == [(request, "staff", "quote")]


def test_keep_failure_never_masks_the_refusal(monkeypatch):
    def boom(*_a):
        raise RuntimeError("db down")

    monkeypatch.setattr("apps.hardware_requests.loan_charges_issue.deposit_quote", boom)
    monkeypatch.setattr("apps.hardware_requests.models.HardwareRequest.objects",
                        SimpleNamespace(select_related=lambda *_: SimpleNamespace(get=lambda pk: object())))
    replay_execute.keep_raised_deposit(SimpleNamespace(payment=SimpleNamespace(pk=1, subject_id=7)), "staff")
