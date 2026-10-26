# Fairfax County City Environment Explorer

A local-first AI Engineer portfolio demo for exploring illustrative Fairfax
County air-quality data. It demonstrates an interactive map, time-series
analysis, location comparisons, evidence-linked summaries, and optional Azure
OpenAI integration. The hosted target is Azure Container Apps.

> **Data disclaimer:** The initial dataset is generated for demonstration. Map
> points and PM2.5 values are not real measurements, forecasts, or live
> monitoring. No public environmental data feed has been integrated or
> validated yet.

## Features

- Explore four Fairfax County-area sample locations on an interactive map.
- Filter sample PM2.5 readings by location and time window.
- Compare location averages and inspect trends over time.
- Generate a deterministic sample summary without cloud credentials, or use an
  Azure OpenAI deployment for a model-generated summary with evidence IDs.
- Inspect source, time range, and summary statistics for each evidence record.

The no-credentials summary is clearly labeled as a deterministic fallback, not
as an AI response. If Azure AI is configured but the service request fails, the
application reports the error rather than silently substituting the fallback.

## Run locally

Requires Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
streamlit run app.py
```

The app is available at `http://localhost:8501`. The interactive map uses
OpenStreetMap tiles and therefore needs an internet connection for its
basemap; the sample observations are generated locally.

Run the focused tests with:

```powershell
pytest
```

## Optional Azure OpenAI summaries

1. Copy `.env.example` to `.env` and set `AZURE_OPENAI_ENDPOINT` to your Azure
   OpenAI resource root and `AZURE_OPENAI_DEPLOYMENT` to a deployed chat model.
2. For local development, sign in with Azure CLI and grant your identity the
   required model inference permission. The app uses `DefaultAzureCredential`.
3. Alternatively, set `AZURE_OPENAI_API_KEY` locally. Do not commit `.env` or
   credentials.
4. Restart the app and click **Generate summary**. Only the selected aggregate
   evidence records are sent to the configured model.

The Azure endpoint follows the OpenAI-compatible v1 API. Model usage may incur
charges. In an Azure-hosted production environment, use managed identity and set
`APP_ENV=production`; do not use a developer credential chain there. See the
[Microsoft Azure OpenAI Python endpoint guidance](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/switching-endpoints).

## Deploy to Azure Container Apps

The deployment uses Bicep and a GitHub Actions workflow with GitHub OIDC. It
creates a Basic Azure Container Registry, Log Analytics workspace, Container
Apps environment, and a publicly accessible HTTPS Container App. The app uses a
managed identity to pull its image; ACR admin credentials are disabled.

### One-time Azure setup

1. Create the Azure resource group in East US 2 (or another supported region).
   The workflow expects this resource group to exist.
2. Create an Entra application/service principal with a federated identity
   credential whose subject is
   `repo:silent-vector-26/city-environment-explorer:environment:azure-production` and whose
   audience is `api://AzureADTokenExchange`. Update the repository portion if
   the GitHub repository is renamed.
3. Grant that principal `Contributor`, `Role Based Access Control Administrator`,
   and `AcrPush` at the deployment resource-group scope. These roles let the
   workflow deploy resources, create the Container App's image-pull role
   assignment, and publish images. Use a dedicated deployment identity and
   review the permissions with your Azure administrator.
4. In GitHub, create the `azure-production` Environment. Configure required
   reviewers, prevent self-review if available, and restrict deployment
   branches to `main`. **The approval gate is enforced by GitHub Environment
   protection settings; the workflow pauses for approval only after those
   reviewers are configured.**
5. Add these **Environment variables** to `azure-production`:
   `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, and
   `AZURE_RESOURCE_GROUP`. `AZURE_LOCATION` is optional and defaults to
   `eastus2`. Optionally set `AZURE_OPENAI_ENDPOINT` and
   `AZURE_OPENAI_DEPLOYMENT` to enable Azure AI summaries. Do not put credentials
   or keys in workflow files or client-side code.
6. If Azure AI summaries are enabled, grant the deployed Container App's
   system-assigned identity the `Cognitive Services OpenAI User` role on the
   Azure OpenAI resource. The app uses managed identity in Azure.

### Deploy

The workflow at
[`deploy-azure-container-app.yml`](.github/workflows/deploy-azure-container-app.yml)
runs on pushes to `main` and can also be started with **Actions → Deploy Azure
Container App → Run workflow**. It first runs tests and builds the container.
After those checks pass, the deployment job waits for approval in
`azure-production`, then provisions the infrastructure, builds and pushes the
container image, deploys the app, and prints its HTTPS endpoint.

The Bicep template is [`infra/main.bicep`](infra/main.bicep). It supports
scale-to-zero with a small replica ceiling; the first request after inactivity
may experience a cold start. Container Apps, registry storage, and log ingestion
can incur charges. Review current pricing and configure budget alerts before
deploying. The workflow files are prepared but have not been run against Azure.

## Next steps

- Validate a suitable public air-quality source and its Fairfax County coverage,
  data terms, freshness, and access requirements before representing it as live.
- Replace or supplement generated sample observations with a validated source,
  retaining source and observation-time metadata.
- Assess deployment and operating costs before adding Azure hosting.

See the [Software Requirements Specification](docs/InsightMiner_SRS_v1.0.0.md)
for the agreed scope, requirements, assumptions, and acceptance criteria.
