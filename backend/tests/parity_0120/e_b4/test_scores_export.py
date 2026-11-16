"""E-B4 (D6): the scores CSV carries scores and judge names, never comments, notes or emails."""
from types import SimpleNamespace
from unittest.mock import Mock

from apps.events.judging import exports
from apps.events.judging.views_e_b4 import _lines

CALCULATION = {"rows": [
    {"snapshot_id": 2, "n": 3, "rank": 2, "raw_score": "3.00000000", "zscore": "-0.10000000", "score": "3.00000000",
     "criterion_averages": {"impact": "3.00000000"}},
    {"snapshot_id": 1, "n": 3, "rank": 1, "raw_score": "4.50000000", "zscore": "0.90000000", "score": "4.50000000",
     "criterion_averages": {"impact": "4.50000000"}}]}


def install(monkeypatch, *, names):
    round = SimpleNamespace(pk=5, key="final", mode="weighted_1_5",
                            configuration={"criteria": [{"key": "impact", "label": "Impact"}]})
    rounds = Mock()
    rounds.exclude.return_value.order_by.return_value = [round]
    monkeypatch.setattr(exports, "JudgingRound", SimpleNamespace(objects=Mock(filter=Mock(return_value=rounds))))
    monkeypatch.setattr(exports, "round_calculation", lambda r: CALCULATION)
    assignments = [SimpleNamespace(submission_snapshot_id=1, judge_role_assignment_id=90),
                   SimpleNamespace(submission_snapshot_id=1, judge_role_assignment_id=91)]
    monkeypatch.setattr(exports, "JudgeAssignment", SimpleNamespace(
        objects=Mock(filter=Mock(return_value=Mock(order_by=Mock(return_value=assignments))))))
    judges = {90: SimpleNamespace(member_id=1), 91: SimpleNamespace(member_id=2)}
    titles = {1: "Robot arm", 2: "Compost bin"}
    monkeypatch.setattr(exports, "runtime", lambda: SimpleNamespace(
        judge=lambda pk: judges[pk], snapshot=lambda pk: SimpleNamespace(title=titles[pk])))
    monkeypatch.setattr(exports, "_judge_names", lambda ids, names_visible: (
        {1: "Asha", 2: "Ben"} if names_visible else {1: "Judge 1", 2: "Judge 2"}))


def test_rows_are_ranked_and_carry_raw_adjusted_and_per_criterion_scores(monkeypatch):
    install(monkeypatch, names=True)
    rows = list(exports.scores_rows(object(), names_visible=True))
    assert [row["project"] for row in rows] == ["Robot arm", "Compost bin"]
    assert rows[0]["raw_score"] == "4.50000000" and rows[0]["adjusted_score"] == "0.90000000"
    assert rows[0]["average Impact"] == "4.50000000"
    assert rows[0]["judges"] == "Asha; Ben"
    assert rows[1]["judges"] == ""


def test_judge_names_are_hidden_without_personal_data_access(monkeypatch):
    install(monkeypatch, names=False)
    assert list(exports.scores_rows(object(), names_visible=False))[0]["judges"] == "Judge 1; Judge 2"


def test_csv_has_no_comment_note_or_email_column_and_neutralises_formulas(monkeypatch):
    install(monkeypatch, names=True)
    columns = exports.scores_columns(object())
    assert not {"notes", "comments", "email", "team_feedback"} & {c.casefold() for c in columns}
    rows = [{**row, "project": "=HYPERLINK(\"x\")"} for row in exports.scores_rows(object(), names_visible=True)]
    text = b"".join(_lines(columns, rows)).decode()
    assert text.splitlines()[0].startswith("round,mode,rank,project,reviews,raw_score,adjusted_score,score,average Impact,judges")
    assert "'=HYPERLINK" in text and ",=HYPERLINK" not in text
