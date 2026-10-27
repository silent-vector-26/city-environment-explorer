from types import SimpleNamespace
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import cee.telemetry as telemetry
from cee.ai import generate_grounded_summary


def test_telemetry_is_disabled_without_connection_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    assert telemetry.configure_telemetry() is False


def test_telemetry_setup_failure_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=x")
    monkeypatch.setattr(telemetry, "_configured", False)
    with patch(
        "azure.monitor.opentelemetry.configure_azure_monitor",
        side_effect=RuntimeError("boom"),
    ):
        assert telemetry.configure_telemetry() is False


def test_summary_span_has_metadata_but_no_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "tracer", provider.get_tracer("test"))
    monkeypatch.setattr("cee.ai.tracer", provider.get_tracer("test"))
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setenv("APP_ENV", "development")

    evidence = [{"evidence_id": "S1", "location": "SECRET-SITE", "record_type": "observed"}]
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Summary text. [S1]"),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
    )
    with patch("openai.OpenAI") as client_class:
        client_class.return_value.chat.completions.create.return_value = response
        generate_grounded_summary(evidence)

    (span,) = exporter.get_finished_spans()
    attrs = dict(span.attributes)
    assert span.name == "cee.generate_summary"
    assert attrs["gen_ai.usage.input_tokens"] == 11
    assert attrs["gen_ai.usage.output_tokens"] == 7
    assert attrs["cee.outcome"] == "ok"
    assert "SECRET-SITE" not in str(attrs)
    assert "Summary text" not in str(attrs)
    assert trace is not None
