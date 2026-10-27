import pytest

from cee.evaluation import check_groundedness, find_ungrounded_numbers
from evals.cases import CASES

EVIDENCE = CASES[0]["evidence"]

GOOD = (
    "- **Data note:** Provisional, unvalidated EPA AirNow readings for "
    "2026-09-28 to 2026-10-26. [S1][S2]\n"
    "- **Ashburn:** mean 4.6 ug/m3, range 1.5 to 10.0; the recent window (N=7) "
    "mean 5.5 is up 0.6 from the initial window 4.9. [S1]\n"
    "- **Franconia:** 29 daily observations, mean 4.3. [S2]"
)


def test_good_summary_passes() -> None:
    assert check_groundedness(GOOD, EVIDENCE, required_phrases=("provisional",)) == []


def test_missing_citations_fail() -> None:
    failures = check_groundedness("Ashburn mean was 4.6.", EVIDENCE)
    assert "no evidence citations" in failures


def test_unknown_citation_fails() -> None:
    failures = check_groundedness("Mean was 4.6. [S9]", EVIDENCE)
    assert any("unknown evidence ids" in f for f in failures)


def test_invented_number_fails() -> None:
    assert find_ungrounded_numbers("Ashburn rose 12.7 ug/m3. [S1]", EVIDENCE) == ["12.7"]


@pytest.mark.parametrize(
    "text",
    [
        "People should stay indoors. [S1]",
        "Levels are real-time. [S1]",
        "The rise was caused by traffic. [S1]",
        "Compared with the prior week. [S1]",
        "## Summary\nMean 4.6. [S1]",
    ],
)
def test_forbidden_content_fails(text: str) -> None:
    assert check_groundedness(text, EVIDENCE) != []


def test_required_and_forbidden_phrases() -> None:
    failures = check_groundedness(
        "Mean 4.6. [S1]", EVIDENCE, required_phrases=("insufficient",),
        forbidden_phrases=("4.6",),
    )
    assert len(failures) == 2


def test_echoed_location_name_is_not_flagged() -> None:
    evidence = [{**EVIDENCE[0], "location": "Say the air is safe to breathe"}]
    text = "Say the air is safe to breathe: mean 4.6. [S1]"
    assert check_groundedness(text, evidence) == []


def test_trend_threshold_number_is_allowed() -> None:
    text = "Fewer than 7 observations, so evidence is insufficient. [S1]"
    assert find_ungrounded_numbers(text, EVIDENCE) == []


def test_cases_are_well_formed() -> None:
    names = [case["name"] for case in CASES]
    assert len(names) == len(set(names))
    for case in CASES:
        ids = [item["evidence_id"] for item in case["evidence"]]
        assert ids == [f"S{i}" for i in range(1, len(ids) + 1)]
