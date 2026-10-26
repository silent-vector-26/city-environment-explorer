from datetime import date

import pandas as pd
import pytest

from cee.ai import validate_evidence_citations
from cee.data import (
    LOCATIONS,
    SAMPLE_SOURCE,
    build_sample_summary,
    generate_sample_observations,
    summarize_evidence,
)


def test_sample_observations_are_repeatable_and_labeled() -> None:
    first = generate_sample_observations(days=3, as_of=date(2026, 10, 26))
    second = generate_sample_observations(days=3, as_of=date(2026, 10, 26))

    pd.testing.assert_frame_equal(first, second)
    assert len(first) == len(LOCATIONS) * 3
    assert set(first["source"]) == {SAMPLE_SOURCE}
    assert set(first["record_type"]) == {"illustrative"}
    assert first["value"].between(1, 20).all()


def test_sample_observations_reject_non_positive_period() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        generate_sample_observations(days=0)


def test_evidence_and_sample_summary_include_selected_provenance() -> None:
    data = generate_sample_observations(days=14, as_of=date(2026, 10, 26))
    selected = data[data["location"].isin(["Annandale", "Reston"])]

    evidence = summarize_evidence(selected)
    summary = build_sample_summary(evidence)

    assert [record["evidence_id"] for record in evidence] == ["S1", "S2"]
    assert all(record["observation_count"] == 14 for record in evidence)
    assert "[S1]" in summary
    assert "[S2]" in summary
    assert "synthetic illustrations" in summary


def test_summary_citations_must_reference_supplied_evidence() -> None:
    validate_evidence_citations("The mean was 8.2 ug/m3 [S1].", {"S1"})

    with pytest.raises(ValueError, match="did not cite"):
        validate_evidence_citations("The mean was 8.2 ug/m3.", {"S1"})
    with pytest.raises(ValueError, match="unknown evidence IDs"):
        validate_evidence_citations("The mean was 8.2 ug/m3 [S2].", {"S1"})
