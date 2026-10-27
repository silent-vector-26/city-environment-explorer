# Fairfax County City Environment Explorer

## Software Requirements Specification

| Field | Value |
| --- | --- |
| Document version | 1.0.0 |
| Date | October 26, 2026 |
| Status | MVP implementation started; Container Apps deployment target approved |
| Audience | AI Engineer portfolio reviewers, demo users, and implementers |
| Document ID | CEE-SRS-001 |

> This document specifies the desired MVP behavior. The initial local prototype
> uses generated sample observations and is not a live environmental service.
> The legacy filename is retained to preserve the existing document path.

## 1. Purpose and scope

The City Environment Explorer is a portfolio demo for exploring environmental
conditions in Fairfax County, Virginia. It should demonstrate a useful,
responsible path from public environmental data to geographic exploration and
AI-generated explanations grounded in evidence.

The minimum viable demo (MVP) comprises:

1. An interactive map for exploring available data by location.
2. Time trends for selected environmental measures and locations.
3. Comparison of selected locations.
4. AI-generated summaries that cite or otherwise expose the supporting source
   records, source references, and relevant observation times.

The target is a responsive web application, developed local-first and hosted on
Azure Container Apps for the portfolio demo. The initial implementation uses
Python and Streamlit, with Bicep infrastructure and an approval-gated GitHub
Actions deployment. It favors low operating cost and avoids personal-data
collection. Azure OpenAI summaries are optional; the app has a clearly labeled
deterministic fallback when a model is not configured.

### 1.1 Out of scope

- A production-grade environmental monitoring or emergency alert service.
- Guaranteed real-time coverage, comprehensive county-wide sensor coverage, or
  prediction/forecasting beyond what a validated source provides.
- User accounts, personalization, social features, or precise location tracking.
- Unvalidated data integrations and paid data subscriptions.
- Treating AI-generated text as authoritative environmental, health, or safety
  advice.

## 2. Users and use cases

### 2.1 Target users

- **Portfolio reviewer:** evaluates the demo’s user experience, data handling,
  and grounded AI behavior.
- **Curious resident or visitor:** explores available environmental information
  and compares places in Fairfax County.
- **Demo operator/developer:** configures or runs the local-first demo and
  verifies its data sources.

### 2.2 Primary use cases

- Select a map location or area and inspect available environmental observations
  and their provenance.
- Choose a measure and time range to see its historical trend, when supported
  by validated data.
- Compare two or more locations using comparable measures and time periods.
- Request a short explanation or summary and inspect the evidence supporting it.
- Understand when results are incomplete, stale, unavailable, or not comparable.

## 3. Product overview and constraints

The system is expected to present geographic context, environmental observations,
and derived summaries through a responsive browser interface. Data may be loaded
from approved public feeds or, if live access is unsuitable, from clearly labeled
sample data. In either case, each displayed result must distinguish observations
from estimates, sample values, and AI-generated explanations.

Implementation should be local-first and cost-conscious. Azure compatibility is
a design option, not a deployment commitment. The initial implementation uses a
Python Streamlit application, generated sample observations, and an optional
Azure OpenAI integration. It must not depend on an unvalidated external API or
silently misstate the availability, freshness, or geographic coverage of its
data.

## 4. Functional requirements

Priority uses **Must**, **Should**, and **Could** for the MVP baseline.

### 4.1 Map and exploration

- **CEE-FR-001 (Must):** The application shall provide an interactive map centered
  on Fairfax County and identify the geographic extent of displayed data.
- **CEE-FR-002 (Must):** A user shall be able to select a location or map feature
  and view the environmental information available for it.
- **CEE-FR-003 (Must):** Map layers and symbols shall identify the measure and
  units represented, where supplied by the source.
- **CEE-FR-004 (Must):** The interface shall communicate when a location has no
  applicable data, rather than implying a zero or normal reading.

### 4.2 Trends and comparison

- **CEE-FR-005 (Must):** A user shall be able to view a time series for an
  available measure and location over a selectable supported time range.
- **CEE-FR-006 (Must):** A user shall be able to compare at least two selected
  locations for the same measure and a comparable time period.
- **CEE-FR-007 (Must):** Trend and comparison views shall identify units,
  observation period, and data source when those attributes are available.
- **CEE-FR-008 (Should):** The interface should explain when different source
  coverage, sampling intervals, or missing records limit a comparison.

### 4.3 Grounded AI summaries

- **CEE-FR-009 (Must):** A user shall be able to request a concise natural-language
  summary of selected, available environmental information.
- **CEE-FR-010 (Must):** A summary shall be grounded only in data made available
  to the summarization flow for the current request; it shall not invent
  observations or imply unavailable data was checked.
- **CEE-FR-011 (Must):** Each summary shall expose supporting evidence through
  source references and the relevant location and observation period. Where
  supported by source metadata, evidence should include observation timestamps
  and links to the original source.
- **CEE-FR-012 (Must):** The application shall distinguish AI-generated
  interpretation from measured observations and shall state when evidence is
  insufficient to answer.
- **CEE-FR-013 (Must):** AI summaries shall not be presented as medical, safety,
  regulatory-compliance, or emergency guidance.

### 4.4 Data and source handling

- **CEE-FR-014 (Must):** Each integrated source shall have documented attribution,
  access method, geographic and temporal coverage, update expectations, units,
  and known limitations before it is used in the demo.
- **CEE-FR-015 (Must):** The application shall display source and freshness
  information where available and identify sample or cached data as such.
- **CEE-FR-016 (Must):** If a source is unavailable, stale, or missing required
  fields, the application shall report the limitation and avoid presenting the
  affected result as current or complete.
- **CEE-FR-017 (Should):** Data acquisition and normalization should be isolated
  from presentation so that validated sources can be added or replaced without
  changing the user-facing meaning of measures.
- **CEE-FR-018 (Should):** The application should persist hourly observations
  for up to 90 days so a restarted instance can show stored data immediately,
  without waiting for a full source download.
- **CEE-FR-019 (Should):** After the first load, the application should request
  only data newer than what is stored, re-requesting a 48-hour overlap because
  the source revises provisional values. If the source is unavailable, stored
  data shall be served and identified as such.

## 5. Data sources and validation plan

The primary provider is the EPA AirNow API (monitoring-site hourly data service),
validated for Fairfax County coverage: three monitoring sites (Ashburn, Franconia
and Northern VA Near Road) return hourly PM2.5 for 30 days. The retired AirNow ZIP
and lat/long endpoints are not used. Readings are provisional and unvalidated and
shall be labeled as such. The other candidates below remain unconfirmed.

| Candidate | Intended use | Required validation before adoption |
| --- | --- | --- |
| EPA AirNow (adopted) | Hourly PM2.5 by monitoring site, aggregated to local-day means | Follow AirNow data use guidelines; cache results; retain site, agency and timestamp metadata |
| Official Fairfax County GIS portal | County geography, boundaries, and suitable public GIS layers | Confirm layer relevance, service/API availability, licensing and attribution, geographic detail, update cadence, and technical access constraints |
| Other regional or federal feeds | Potential weather or other environmental observations | Identify the specific provider and measures; verify API availability, credentials, coverage, timestamps, units, update frequency, quality, terms, and cost |
| Clearly labeled sample data | Fallback when AirNow is unavailable or no key is configured | Document that values are illustrative, avoid implying they are current observations, and retain provenance/metadata needed for UI and test scenarios |

The demo shall not label sample data as live or real.

### 5.1 Minimum data fields

For each observation, retain or derive where available:

- Measure identifier/name and unit.
- Value and observation time (including time zone or an unambiguous standard).
- Geographic point, area, or associated feature, with the source’s spatial
  resolution made clear.
- Provider/source identifier and source record or URL for provenance.
- Retrieval or last-updated time, distinct from observation time.
- Quality, status, or missingness indicators supplied by the provider.

Missing fields shall be represented as unknown or unavailable, not fabricated.
Any transformation, aggregation, or unit conversion affecting presentation
should be documented and testable.

## 6. External interfaces and proposed architecture

### 6.1 User interface

The application shall provide a responsive web UI for map exploration, trend
inspection, location comparison, and evidence-backed summaries. Map, chart, and
summary views shall share the selected locations, measures, and time range so
that the user can understand what the summary describes.

### 6.2 Data and AI interfaces

The implementation may use source adapters to retrieve, validate, and normalize
approved GIS and environmental data. An AI service, if used, shall receive only
the relevant selected data and provenance needed to generate a grounded summary.
The design shall make source evidence available alongside generated text rather
than relying on a model’s unaided knowledge for current conditions.

The AirNow API key is a credential stored as a GitHub Environment secret and a
Container Apps secret. It must not be committed to the repository or exposed in
client-side code or error messages.

Observations come from AirNow. Because the service can take over a minute, an
in-process background job loads the data at container start and refreshes it
hourly; requests read the last good snapshot. When no key is configured or no
snapshot can be loaded, the app shows clearly labeled sample observations.
Azure OpenAI summaries (`gpt-5.2`) use an OpenAI-compatible v1 endpoint with the
app's managed identity, return Markdown that cites evidence IDs, and are disabled
until an endpoint and deployment are configured. When no model is configured, the
app may show a deterministic summary that is explicitly labeled as non-AI output.
A configured model request failure must be surfaced rather than hidden by the
fallback.

### 6.3 Deployment direction

The MVP shall be deployable to Azure Container Apps in East US 2 by default,
with the region configurable. Infrastructure shall be described in Bicep under
`infra/`; the deployment shall use an Azure Container Registry, a Container Apps
managed environment, Log Analytics, and a managed identity for image pulls.
Public ingress shall use HTTPS. The app shall keep at least one replica running so
the in-memory data cache stays warm, with a configurable, bounded maximum
replica count.

GitHub Actions shall test the application and build the container before
deployment. It shall deploy the app using GitHub OIDC rather than long-lived
Azure credentials. The deployment job shall target a GitHub Environment named
`azure-production`. Required reviewers and branch protection must be configured
in GitHub repository settings; a workflow reference to an Environment alone
does not enforce human approval. Azure deployment identity configuration and
permissions shall be documented. The workflow shall not deploy until approval
is granted.

The initial workflow deploys infrastructure and application code. No resources
are provisioned as part of local development or by simply editing the workflow.
The owner must trigger or merge an eligible workflow run and approve its
deployment through GitHub.

## 7. Non-functional requirements

### 7.1 Usability and accessibility

- **CEE-NFR-001 (Must):** The primary map, trend, comparison, and evidence flows
  shall be usable on common desktop and mobile viewport sizes.
- **CEE-NFR-002 (Should):** Essential information conveyed by color on the map or
  charts should also be available through labels, patterns, text, or an
  accessible data view.
- **CEE-NFR-003 (Should):** Keyboard navigation and screen-reader semantics
  should be considered for core controls and source evidence.

### 7.2 Privacy and security

- **CEE-NFR-004 (Must):** The MVP shall not require user accounts or collect
  personally identifying information.
- **CEE-NFR-005 (Must):** The application shall not collect precise user location
  by default. Any future location feature requires explicit user action and a
  separate privacy decision.
- **CEE-NFR-006 (Must):** Secrets and provider credentials shall be kept outside
  source control and browser-delivered code.
- **CEE-NFR-006a (Must):** GitHub Actions shall use OIDC federation for Azure
  login and shall not require a long-lived Azure client secret.
- **CEE-NFR-006b (Must):** Production container image pulls shall use managed
  identity and Azure RBAC; ACR admin credentials shall remain disabled.
- **CEE-NFR-006c (Must):** The deployment workflow shall target an approval-
  protected GitHub Environment; reviewers and eligible branches shall be
  configured in repository settings.
- **CEE-NFR-007 (Should):** Logs should avoid recording user-entered prompts or
  other potentially identifying content unless necessary, disclosed, and
  explicitly approved.

### 7.3 Reliability and transparency

- **CEE-NFR-008 (Must):** The user shall be able to distinguish observation time,
  retrieval time, sample data, and AI-generated explanation where applicable.
- **CEE-NFR-009 (Must):** Source errors and data gaps shall result in an
  informative unavailable/limited state rather than fabricated values.
- **CEE-NFR-010 (Must):** The MVP shall document known limitations in geographic
  coverage, temporal coverage, source quality, and interpretation.

### 7.4 Cost and maintainability

- **CEE-NFR-011 (Must):** The MVP shall favor free or low-cost public data and
  consumption-based hosting; no paid data dependency is assumed.
- **CEE-NFR-012 (Must):** Any usage-based AI or cloud service shall have its
  expected cost and a means to limit or disable usage reviewed before use.
- **CEE-NFR-013 (Should):** Data-source integrations should be modular and
  documented so a provider can be replaced if terms, availability, or cost
  change.
- **CEE-NFR-014 (Should):** Persistent storage shall use a consumption-priced
  service with keyless (managed identity) access and automatic expiry of
  old records.

## 8. Acceptance criteria

The MVP scope is considered demonstrable when:

1. A user can explore the available Fairfax County geography and see what data
   coverage is present or absent.
2. A user can inspect a supported measure over time and compare at least two
   locations when comparable data exists.
3. Displayed observations include available units, source, and time metadata;
   sample data, if used, is unmistakably labeled.
4. A user can request a summary of selected data and inspect source evidence
   relevant to that summary.
5. When data is unavailable, stale, incomplete, or insufficient for a
   comparison or summary, the UI communicates that limitation without inventing
   facts.
6. Core flows work at desktop and mobile viewport sizes, and no personal data or
   precise location is collected by default.
7. The selected data providers, access/credential needs, coverage, terms, and
   expected operating costs have been reviewed and documented before any live
   integration is represented as available.
8. The container image can be built and deployed to the configured Container
   App by the GitHub Actions workflow after approval through the protected
   `azure-production` Environment.
9. The deployed app is reachable through HTTPS ingress, and no long-lived Azure
   credential is stored in GitHub Actions secrets.

## 9. Assumptions, open decisions, and risks

### 9.1 Assumptions

- Public geographic and environmental data may be suitable for a portfolio demo,
  but availability and terms have not yet been verified.
- A local-first implementation and optional Python backend are acceptable.
- Public sample data may be used when live data access is not practical, provided
  the sample status is clear to users.
- The project is an educational/portfolio demonstration, not an operational
  environmental authority.

### 9.2 Decisions deferred

- Additional measures and environmental domains to include after source review.
- Persisting AirNow history across restarts, and evaluation/tracing of summaries.
- Azure model deployment selection and budget ceiling.
- Production data feeds, user analytics, or location-based features.

### 9.3 Principal risks

- Candidate sources may not cover Fairfax County at useful spatial or temporal
  resolution, or may require credentials, have restrictive terms, or incur cost.
- Azure resource pricing, regional availability, and subscription quota may
  affect deployment; verify them before the first approved deployment.
- Heterogeneous units, sampling intervals, and missing observations may make
  location comparisons misleading.
- A generated summary may overstate what observations support; evidence display,
  constrained inputs, and insufficient-evidence behavior are required to reduce
  this risk.
- Environmental observations can be incomplete or delayed; the demo must not
  imply real-time or comprehensive monitoring without verification.

## 10. Glossary

| Term | Definition |
| --- | --- |
| Observation | A value reported or measured by a source for a location and time |
| Source evidence | Provenance and supporting records used to substantiate a displayed result or AI summary |
| Sample data | Illustrative data used for demonstration and not represented as a current real-world observation |
| Freshness | The relationship between a record’s observation time, source update time, and retrieval time |
| Grounded summary | AI-generated text based on selected, available data with evidence exposed to the user |
