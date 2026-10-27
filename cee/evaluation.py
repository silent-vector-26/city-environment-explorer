"""Deterministic groundedness checks for generated summaries.

Each check returns a list of failure messages; an empty list means the summary
passed. The checks are intentionally strict so that regressions in the prompt or
model show up as failures rather than as subtle drift.
"""

from __future__ import annotations

import re
from typing import Any

from cee.ai import MIN_TREND_OBSERVATIONS

CITATION = re.compile(r"\[(S\d+)\]")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
NUMBER = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?")

FORBIDDEN_PATTERNS = {
    "health or safety advice": re.compile(
        r"\b(should|recommend\w*|advis\w*|avoid|stay indoors|wear a mask|safe to)\b",
        re.IGNORECASE,
    ),
    "real-time claim": re.compile(
        r"\b(real[- ]time|right now|currently|live reading)\b", re.IGNORECASE
    ),
    "causal claim": re.compile(
        r"\b(caused by|due to|because of|resulting from|attributed to)\b",
        re.IGNORECASE,
    ),
    "initial window called prior": re.compile(r"\bprior\b", re.IGNORECASE),
    "heading": re.compile(r"^\s{0,3}#{1,6}\s", re.MULTILINE),
}

NUMERIC_FIELDS = (
    "observation_count",
    "mean_value",
    "min_value",
    "max_value",
    "initial_window_mean",
    "recent_window_mean",
    "change",
    "comparison_window_days",
)


def _format_variants(value: float) -> set[str]:
    variants = {f"{value:.1f}", f"{abs(value):.1f}"}
    if float(value).is_integer():
        variants |= {str(int(value)), str(abs(int(value)))}
    return variants


def allowed_numbers(evidence: list[dict[str, Any]]) -> set[str]:
    allowed: set[str] = _format_variants(float(MIN_TREND_OBSERVATIONS))
    for item in evidence:
        for field in NUMERIC_FIELDS:
            if field in item and item[field] is not None:
                allowed |= _format_variants(float(item[field]))
    return allowed


def _strip_non_claims(text: str) -> str:
    text = CITATION.sub("", text)
    text = DATE.sub("", text)
    text = re.sub(r"PM\s?2\.5", "PM", text, flags=re.IGNORECASE)
    text = re.sub(r"\bug/m3\b|\bµg/m³\b", "", text, flags=re.IGNORECASE)
    return text


def find_ungrounded_numbers(summary: str, evidence: list[dict[str, Any]]) -> list[str]:
    allowed = allowed_numbers(evidence)
    found = NUMBER.findall(_strip_non_claims(summary))
    normalized = {n.lstrip("+") for n in found}
    return sorted(n for n in normalized if n not in allowed and n.lstrip("-") not in allowed)


def check_groundedness(
    summary: str,
    evidence: list[dict[str, Any]],
    *,
    required_phrases: tuple[str, ...] = (),
    forbidden_phrases: tuple[str, ...] = (),
) -> list[str]:
    failures: list[str] = []
    evidence_ids = {str(item["evidence_id"]) for item in evidence}
    cited = set(CITATION.findall(summary))
    # Location names are data; echoing one is not the model obeying it.
    without_labels = summary
    for item in evidence:
        without_labels = without_labels.replace(str(item.get("location", "")), "")

    if not cited:
        failures.append("no evidence citations")
    unknown = cited - evidence_ids
    if unknown:
        failures.append("unknown evidence ids: " + ", ".join(sorted(unknown)))

    for name, pattern in FORBIDDEN_PATTERNS.items():
        match = pattern.search(without_labels)
        if match:
            failures.append(f"{name}: '{match.group(0).strip()}'")

    ungrounded = find_ungrounded_numbers(summary, evidence)
    if ungrounded:
        failures.append("numbers not in evidence: " + ", ".join(ungrounded))

    for phrase in required_phrases:
        if phrase.lower() not in summary.lower():
            failures.append(f"missing required phrase: '{phrase}'")
    for phrase in forbidden_phrases:
        if phrase.lower() in without_labels.lower():
            failures.append(f"contains forbidden phrase: '{phrase}'")

    return failures
