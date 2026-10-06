"""The shared closed vocabularies: disciplines, reliability and candidate status."""

from __future__ import annotations

from gwylio.collection import model
from gwylio.shared.vocabulary import CandidateStatus, Discipline, MatchedBy, Reliability


def test_reliability_letters_and_labels() -> None:
    assert [r.value for r in Reliability] == ["A", "B", "C", "D", "E", "F"]
    assert Reliability.A.label == "completely reliable"
    assert Reliability.B.label == "usually reliable"
    assert Reliability.F.label == "cannot be judged"
    assert all(r.label for r in Reliability)


def test_disciplines_and_which_are_reserved() -> None:
    assert [d.value for d in Discipline] == [
        "osint_web",
        "osint_feed",
        "osint_site",
        "osint_academic",
        "geoint",
        "sensor",
    ]
    assert {d for d in Discipline if d.reserved} == {Discipline.GEOINT, Discipline.SENSOR}
    assert all(d.meaning.endswith(".") for d in Discipline)


def test_candidate_status_and_matched_by() -> None:
    assert [s.value for s in CandidateStatus] == ["new", "seen_before", "reinforcement"]
    assert all(s.meaning for s in CandidateStatus)
    assert [m.value for m in MatchedBy] == ["url", "title"]


def test_collection_model_re_exports_the_shared_enums() -> None:
    assert model.Discipline is Discipline
    assert model.Reliability is Reliability
    assert model.CandidateStatus is CandidateStatus
    assert model.MatchedBy is MatchedBy
