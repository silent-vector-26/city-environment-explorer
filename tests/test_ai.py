from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from cee.ai import azure_ai_is_configured, generate_grounded_summary


@pytest.fixture
def evidence() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "S1",
            "location": "Fairfax",
            "measure": "PM2.5 24-hour average",
            "unit": "ug/m3",
            "start_date": "2026-10-01",
            "end_date": "2026-10-30",
            "observation_count": 30,
            "mean_value": 8.2,
            "source": "Synthetic sample data",
        }
    ]


def test_azure_ai_is_disabled_without_endpoint_or_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

    assert not azure_ai_is_configured()


def test_azure_ai_rejects_partial_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

    with pytest.raises(RuntimeError, match="Set both"):
        azure_ai_is_configured()


def test_grounded_summary_uses_configured_deployment_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
    evidence: list[dict[str, object]],
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "demo-model")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "local-test-key")
    monkeypatch.setenv("APP_ENV", "development")

    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="The sample mean is 8.2 ug/m3 [S1].")
            )
        ]
    )
    with patch("openai.OpenAI", return_value=client) as openai_client:
        result = generate_grounded_summary(evidence)

    assert result.endswith("[S1].")
    openai_client.assert_called_once_with(
        api_key="local-test-key",
        base_url="https://example.openai.azure.com/openai/v1/",
    )
    client.chat.completions.create.assert_called_once()
    client.close.assert_called_once()


def test_grounded_summary_rejects_unknown_citation_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
    evidence: list[dict[str, object]],
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "demo-model")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "local-test-key")
    monkeypatch.setenv("APP_ENV", "development")

    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="The sample mean is 8.2 ug/m3 [S2].")
            )
        ]
    )
    with patch("openai.OpenAI", return_value=client):
        with pytest.raises(ValueError, match="unknown evidence IDs"):
            generate_grounded_summary(evidence)

    client.close.assert_called_once()
