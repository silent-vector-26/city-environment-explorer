# Fairfax County City Environment Explorer

## Software Design Description

| Field | Value |
| --- | --- |
| Document version | 1.0.0 |
| Date | October 27, 2026 |
| Document ID | CEE-SDD-001 |
| Implements | CEE-SRS-001 ([InsightMiner_SRS_v1.0.0.md](./InsightMiner_SRS_v1.0.0.md)) |
| Status | Describes the implementation merged to `main` (PR #1) |

## 1. Introduction

This document describes how the City Environment Explorer (CEE) satisfies the
requirements in the SRS. It covers the system context, runtime structure, data
flow, AI grounding design, deployment, security, and the design decisions behind
them. Requirement identifiers (CEE-FR-xxx, CEE-NFR-xxx) refer to the SRS.

### 1.1 Design goals

1. **Grounded, honest AI.** Summaries cite only evidence supplied with the request.
2. **Real data, resilient delivery.** Use slow public data without blocking users.
3. **Zero stored secrets for Azure access.** OIDC for CI/CD, managed identity at runtime.
4. **Low cost, simple operations.** One container, in-process cache, no database.
5. **Replaceable parts.** Data source, AI model and hosting are isolated behind small modules.

## 2. System context

```mermaid
flowchart LR
    user([Portfolio reviewer / resident])
    dev([Developer / operator])

    subgraph cee[City Environment Explorer]
        app[Streamlit app in Azure Container Apps]
    end

    airnow[(EPA AirNow API<br/>hourly site data)]
    aoai[Azure OpenAI<br/>gpt-5.2 deployment]
    gh[GitHub<br/>repo + Actions]
    azure[Azure Resource Manager]

    user -->|HTTPS| app
    app -->|HTTPS, API key| airnow
    app -->|HTTPS, managed identity token| aoai
    dev -->|push / approve| gh
    gh -->|OIDC, Bicep, image push| azure
    azure -->|provisions and updates| app
```

## 3. Architecture overview

### 3.1 Logical components

```mermaid
flowchart TB
    subgraph container[Container: python serve.py]
        serve[serve.py<br/>entry point]
        subgraph streamlit[Streamlit process]
            app[app.py<br/>UI: map, charts, summary]
        end
        subgraph pkg[cee package]
            sources[sources.py<br/>AirNow client + aggregation]
            cache[cache.py<br/>LiveDataCache]
            data[data.py<br/>sample data + evidence]
            ai[ai.py<br/>grounded summary]
        end
    end

    serve -->|start warm-up thread| cache
    serve -->|run in-process| streamlit
    cache -->|load_live_observations| sources
    app -->|snapshot / wait_until_ready| cache
    app -->|fallback data| data
    app -->|summarize_evidence| data
    app -->|generate_grounded_summary| ai
    sources -->|HTTPS| airnow[(AirNow)]
    ai -->|HTTPS| aoai[Azure OpenAI]
```

| Module | Responsibility | Key requirements |
| --- | --- | --- |
| [serve.py](../serve.py) | Starts the cache warm-up, then runs Streamlit on `PORT` (default 8501) | CEE-FR-016 |
| [app.py](../app.py) | UI, location selection, charts, labeling of live vs sample data, summary rendering | FR-001 to FR-013, FR-015 |
| [cee/sources.py](../cee/sources.py) | AirNow HTTP client, parsing, hourly to daily aggregation | FR-014, FR-017 |
| [cee/cache.py](../cee/cache.py) | Background load and hourly refresh; keeps last good snapshot | FR-015, FR-016, NFR-009 |
| [cee/data.py](../cee/data.py) | Sample data, evidence building, deterministic fallback summary | FR-010, FR-012, FR-015 |
| [cee/ai.py](../cee/ai.py) | Azure OpenAI call, prompt, citation validation | FR-009 to FR-013 |

### 3.2 Class view

```mermaid
classDiagram
    class LiveDataCache {
        -DataFrame _data
        -str _error
        -datetime _loaded_at
        -Event _ready
        +start(api_key)
        +refresh(api_key) bool
        +wait_until_ready(timeout) bool
        +snapshot() tuple
        -_run(api_key)
    }
    class AirNowError {
        <<exception>>
    }
    class sources {
        <<module>>
        +fetch_hourly_pm25(api_key, ...) list
        +parse_hourly_records(records) DataFrame
        +hourly_to_daily(hourly) DataFrame
        +load_live_observations(api_key, days) DataFrame
    }
    class data {
        <<module>>
        +generate_sample_observations() DataFrame
        +summarize_evidence(observations) list
        +build_sample_summary(evidence) str
    }
    class ai {
        <<module>>
        +azure_ai_is_configured() bool
        +generate_grounded_summary(evidence) str
        +validate_evidence_citations(content, ids)
    }
    class app {
        <<module>>
        +load_observations() tuple
        +nearest_location(...)
        +make_map(...)
    }

    LiveDataCache ..> sources : calls
    sources ..> AirNowError : raises
    app ..> LiveDataCache : reads snapshot
    app ..> data : fallback + evidence
    app ..> ai : summary
```

## 4. Data design

### 4.1 Observation model

Daily observations are a pandas DataFrame derived from hourly AirNow records.

```mermaid
erDiagram
    SITE ||--o{ OBSERVATION : reports
    SOURCE ||--o{ OBSERVATION : provides
    OBSERVATION ||--o{ EVIDENCE_ITEM : summarized_as

    SITE {
        string name
        float latitude
        float longitude
        string agency
    }
    SOURCE {
        string provider
        string kind "live or sample"
        datetime retrieved_at
    }
    OBSERVATION {
        string location
        date local_date
        float pm25_mean "ug per m3, daily mean"
        int hourly_count "minimum 18 per day"
        string source
    }
    EVIDENCE_ITEM {
        string id "cited by the model"
        string location
        float initial_window_mean
        float recent_window_mean
        string period
    }
```

### 4.2 Aggregation rules

- Negative values are AirNow missing-data sentinels and are dropped.
- Hours are grouped into **America/New_York** local days.
- A day with fewer than **18** hourly readings is discarded so that partial days cannot skew trends.
- Evidence values are rounded to one decimal place before they reach the model.
- Missing data stays missing; nothing is interpolated (CEE-NFR-009).

### 4.3 Data source facts

| Item | Value |
| --- | --- |
| Endpoint | AirNow `/aq/data/` (monitoring-site data by bounding box) |
| Parameters | `BBOX` (Fairfax), `dataType=C`, `parameters=PM25` |
| Coverage | Ashburn, Franconia, Northern VA Near Road; 30 days hourly |
| Latency | 12 to 80 seconds, hence the background cache |
| Status | Provisional, unvalidated; labeled in the UI |

## 5. Runtime behavior

### 5.1 Container startup and cache warm-up

```mermaid
sequenceDiagram
    autonumber
    participant CA as Container Apps
    participant S as serve.py
    participant C as LiveDataCache
    participant SRC as sources.py
    participant AN as AirNow API
    participant ST as Streamlit

    CA->>S: start container
    S->>C: start(api_key) in daemon thread
    S->>ST: run Streamlit in-process on PORT
    par background load
        C->>SRC: load_live_observations(key, 30)
        SRC->>AN: GET /aq/data (up to 90 s, one retry)
        AN-->>SRC: hourly PM2.5 records
        SRC-->>C: daily DataFrame
        C->>C: store snapshot, set ready
    and serving
        ST-->>CA: health check responds immediately
    end
    loop every hour
        C->>SRC: refresh
    end
    Note over C: On failure keep last good snapshot and retry after 5 minutes
```

### 5.2 Page load and data-mode selection

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant A as app.py
    participant C as LiveDataCache
    participant D as data.py

    U->>A: open page
    A->>A: AIRNOW_API_KEY configured?
    alt key configured
        A->>C: wait_until_ready(120 s)
        alt snapshot available
            C-->>A: DataFrame, no error, loaded_at
            A-->>U: live data, provisional label, freshness
        else timeout or load error
            C-->>A: None, error text
            A->>D: generate_sample_observations()
            D-->>A: sample DataFrame
            A-->>U: error banner + data labeled as sample
        end
    else no key
        A->>D: generate_sample_observations()
        A-->>U: data labeled as sample
    end
```

### 5.3 Grounded summary generation

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant A as app.py
    participant D as data.py
    participant AI as ai.py
    participant ID as Managed identity / DefaultAzureCredential
    participant M as Azure OpenAI gpt-5.2

    U->>A: Generate summary (selected locations)
    A->>D: summarize_evidence(observations)
    D-->>A: evidence items with ids
    A->>AI: generate_grounded_summary(evidence)
    alt Azure OpenAI configured
        AI->>ID: get token for cognitiveservices scope
        ID-->>AI: bearer token
        AI->>M: chat completion, evidence as data, max_completion_tokens 600
        M-->>AI: Markdown with evidence ids
        AI->>AI: validate_evidence_citations
        alt citations valid
            AI-->>A: Markdown summary
        else unknown id cited
            AI-->>A: error surfaced to user
        end
    else not configured
        AI-->>A: not configured
        A->>D: build_sample_summary(evidence)
        D-->>A: deterministic text labeled non-AI
    end
    A-->>U: st.markdown summary + evidence table
```

### 5.4 Data availability state

```mermaid
stateDiagram-v2
    [*] --> Loading : container start
    Loading --> Live : first load succeeds
    Loading --> Failed : load fails
    Failed --> Live : retry succeeds (5 min)
    Live --> Live : hourly refresh succeeds
    Live --> Stale : refresh fails, last good kept
    Stale --> Live : later refresh succeeds
    Failed --> Failed : retry fails

    note right of Failed
        UI shows sample data with an error banner
    end note
    note right of Stale
        UI keeps showing last good snapshot with its load time
    end note
```

## 6. AI grounding design

| Control | Implementation | Requirement |
| --- | --- | --- |
| Constrained input | Only evidence items for the current selection are sent | FR-010 |
| Evidence as data | Prompt tells the model to treat evidence as data, not instructions | FR-010 |
| Citation | Each claim cites an evidence id; ids are validated after generation | FR-011 |
| Honest limits | Prompt requires an insufficient-evidence statement; real vs sample wording differs | FR-012 |
| Not advice | Prompt and UI state the output is not health or safety guidance | FR-013 |
| No silent fallback | A configured model failure is shown, not hidden behind the fallback | SRS 6.2 |
| Model parameters | GPT-5 family rejects `temperature`; use `max_completion_tokens=600` | design |
| Output format | Markdown with bold labels and bullets, no headings; rendered with `st.markdown` | UX |

## 7. Deployment design

### 7.1 Azure resources

```mermaid
flowchart TB
    subgraph rgapp[Resource group rg-cee-demo, eastus2]
        law[Log Analytics workspace]
        acr[Azure Container Registry<br/>admin disabled]
        env[Container Apps environment]
        pull[User-assigned identity<br/>AcrPull]
        app[Container App<br/>min 1, max 1 replica<br/>system-assigned identity]
        secret[(Secret: airnow-api-key)]
    end
    subgraph rgai[Resource group rg-akhorozov-ai-103]
        oai[Azure AI Services account<br/>gpt-5.2 deployment]
    end

    env --> law
    app --> env
    app -->|pull image| acr
    pull -.->|AcrPull role| acr
    app -.->|uses| pull
    app --> secret
    app ==>|Cognitive Services OpenAI User| oai
    internet((Internet)) -->|HTTPS ingress| app
```

Infrastructure is defined in [infra/main.bicep](../infra/main.bicep). The
cross-resource-group role assignment lives in
[infra/openai-role.bicep](../infra/openai-role.bicep) and is created only when
the account name and resource group parameters are supplied.

### 7.2 CI/CD pipeline

```mermaid
flowchart LR
    push[push to main] --> val

    subgraph val[Job: validate]
        t1[Install deps] --> t2[Run tests]
        t2 --> t3[Validate Bicep]
        t3 --> t4[Build container image]
    end

    val --> gate{{GitHub Environment<br/>azure-production<br/>required reviewer}}
    gate -->|approved| dep

    subgraph dep[Job: deploy]
        d1[Validate configuration] --> d2[OIDC login to Azure]
        d2 --> d3[Provision ACR + environment]
        d3 --> d4[Build and push image]
        d4 --> d5[Provision Container App + role assignment]
        d5 --> d6[Print endpoint]
    end
```

### 7.3 Deployment identity and permissions

```mermaid
flowchart LR
    gha[GitHub Actions job<br/>environment azure-production] -->|OIDC token<br/>subject: repo + environment| entra[Entra app<br/>cee-demo-github-deploy<br/>federated credentials]
    entra --> sp[Service principal]
    sp -->|Contributor<br/>RBAC Administrator<br/>AcrPush| rg1[rg-cee-demo]
    sp -->|CEE Deployment Writer<br/>deployments read, write| rg2[rg-akhorozov-ai-103]
    sp -->|RBAC Administrator| acct[OpenAI account]
```

Two federated credentials exist because, after a repository rename, GitHub
issues an **ID-based** subject (`repo:owner@id/name@id:environment:...`). The
name-based credential is retained but unused.

## 8. Security design

```mermaid
flowchart TB
    subgraph trust[Trust boundaries]
        direction TB
        browser[Browser: no accounts, no PII, no precise location]
        app[Container App]
        secrets[Container Apps secret: AirNow key]
        mi[Managed identity: no stored key for OpenAI]
        oidc[GitHub OIDC: no stored Azure secret]
    end
    browser -->|HTTPS only| app
    app --> secrets
    app --> mi
    oidc --> deploy[Deployment]
```

| Threat or concern | Mitigation | Requirement |
| --- | --- | --- |
| AirNow key leakage | GitHub Environment secret and Container Apps secret; never in source; error text never includes the key | NFR-006 |
| Long-lived Azure credentials | OIDC federation; managed identity at runtime | NFR-006a |
| Registry credentials | ACR admin disabled; image pull by managed identity | NFR-006b |
| Unapproved deployment | Required reviewer and `main`-only branch policy on `azure-production` | NFR-006c |
| Prompt injection via data | Evidence passed as data; citations validated | FR-010, FR-011 |
| Over-privileged deploy identity | Custom role limited to deployment read/write on the OpenAI resource group | least privilege |
| PII | No accounts, no user location, prompts not logged | NFR-004, 005, 007 |

## 9. Reliability, performance and cost

- **Slow upstream:** AirNow takes 12 to 80 seconds; the cache decouples requests from it.
- **Warm cache:** `minReplicas=1` keeps the in-memory snapshot alive; scale-to-zero would force a 1 to 2 minute cold start.
- **Failure handling:** last good snapshot is retained; failures retry in 5 minutes; the UI falls back to labeled sample data.
- **Cost drivers:** one always-on 0.5 vCPU replica, ACR Basic, Log Analytics ingestion, gpt-5.2 tokens per summary (capped at 600 completion tokens). Budget alerts are tracked as DP-52.
- **Limits of the design:** the cache is per replica, so `maxReplicas` is 1; scaling out would warm a second cache and call AirNow twice. Acceptable for a demo.
- **Cost controls:** `maxReplicas=1`, a 1 GB per day Log Analytics cap, and a monthly budget (default $30) with email alerts at 50% and 100% actual and 100% forecast. `CEE_MIN_REPLICAS=0` allows scale-to-zero between demos.

## 10. Testing strategy

| Area | Tests |
| --- | --- |
| Sample data and evidence | [tests/test_data.py](../tests/test_data.py) |
| AI prompt, citation validation | [tests/test_ai.py](../tests/test_ai.py) |
| AirNow parsing, daily aggregation, error handling | [tests/test_sources.py](../tests/test_sources.py) |
| Cache refresh and retry behavior | [tests/test_cache.py](../tests/test_cache.py) |
| Bicep and container build | CI `validate` job |

## 11. Requirement traceability

| Requirement | Design element |
| --- | --- |
| FR-001 to FR-004 | `app.py` map, 3 km click tolerance, explicit no-data message |
| FR-005 to FR-008 | `app.py` charts and comparison from daily observations |
| FR-009 to FR-013 | `ai.py` grounding controls (section 6) |
| FR-014 to FR-016 | `sources.py`, `cache.py`, state model (5.4), labels |
| FR-017, NFR-013 | Source isolated in `sources.py`; UI consumes a DataFrame |
| NFR-006 to 006c | Section 8 |
| NFR-008, NFR-009 | Observation vs retrieval time shown; no interpolation |
| NFR-011, NFR-012 | Section 9; consumption hosting, token cap |
| Deployment (6.3) | Section 7 |

## 12. Design decisions

| # | Decision | Alternatives | Rationale |
| --- | --- | --- | --- |
| D1 | Streamlit single process | React + API | Fastest path; Python end to end |
| D2 | In-process cache | Redis, Blob Storage | No extra cost or infrastructure; persistence is a backlog item (DP-54) |
| D3 | AirNow `/aq/data/` | `ziplatlong` current readings | Only service giving history |
| D4 | Managed identity for OpenAI | API key | No secret to store or rotate |
| D5 | GitHub OIDC | Service principal secret | No long-lived credential |
| D6 | `minReplicas=1` | Scale to zero | Keeps cache warm; accepted cost |
| D7 | Existing AI Services account in another resource group | New account | Reuse exam resource; needs cross-RG role and custom deploy role |
| D8 | Fail loudly when a configured model errors | Silent fallback | Honesty about AI availability |

## 13. Open items

- Tracing and telemetry for AI calls (DP-55).
- Groundedness evaluation set (DP-56).
- Persisting AirNow history (DP-54).
- Budget alerts (DP-52).
- Verifying the production deployment of the real-data release (DP-53).
