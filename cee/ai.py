from __future__ import annotations

import os
import re
from typing import Any


def azure_ai_is_configured() -> bool:
    has_endpoint = bool(os.getenv("AZURE_OPENAI_ENDPOINT", "").strip())
    has_deployment = bool(os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip())
    if has_endpoint != has_deployment:
        raise RuntimeError(
            "Set both AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT, "
            "or leave both unset."
        )
    return has_endpoint


def generate_grounded_summary(evidence: list[dict[str, Any]]) -> str:
    if not azure_ai_is_configured():
        raise RuntimeError(
            "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT to enable Azure AI."
        )
    if not evidence:
        raise ValueError("At least one evidence record is required.")

    from azure.identity import (
        DefaultAzureCredential,
        ManagedIdentityCredential,
        get_bearer_token_provider,
    )
    from openai import OpenAI

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    credential = None

    is_production = os.getenv("APP_ENV", "development").lower() == "production"
    if api_key and not is_production:
        client = OpenAI(
            api_key=api_key,
            base_url=f"{endpoint}/openai/v1/",
        )
    else:
        credential = (
            ManagedIdentityCredential()
            if is_production
            else DefaultAzureCredential()
        )
        token_provider = get_bearer_token_provider(
            credential, "https://ai.azure.com/.default"
        )
        client = OpenAI(
            api_key=token_provider,
            base_url=f"{endpoint}/openai/v1/",
        )

    evidence_ids = {str(item["evidence_id"]) for item in evidence}
    try:
        response = client.chat.completions.create(
            model=deployment,
            temperature=0.1,
            max_completion_tokens=350,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a concise environmental data summary using only the "
                        "provided evidence records. Do not infer causes, make health "
                        "or safety recommendations, or describe the data as real-time. "
                        "State that values are synthetic illustrations. Cite every "
                        "factual comparison with its exact evidence ID in brackets, "
                        "such as [S1]. If evidence is insufficient, say so."
                    ),
                },
                {
                    "role": "user",
                    "content": str(evidence),
                },
            ],
        )
    finally:
        client.close()
        if credential is not None:
            credential.close()

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("Azure AI returned an empty summary.")

    validate_evidence_citations(content, evidence_ids)
    return content.strip()


def validate_evidence_citations(content: str, evidence_ids: set[str]) -> None:
    cited_ids = set(re.findall(r"\[(S\d+)\]", content))
    if not cited_ids:
        raise ValueError("Azure AI summary did not cite any evidence records.")
    unknown_ids = cited_ids - evidence_ids
    if unknown_ids:
        raise ValueError(
            "Azure AI summary cited unknown evidence IDs: "
            + ", ".join(sorted(unknown_ids))
        )
