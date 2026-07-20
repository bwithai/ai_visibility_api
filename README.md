# AI VISIBILITY API - Backend

## Requirements

* [Docker](https://www.docker.com/).
* [uv](https://docs.astral.sh/uv/) for Python package and environment management.

## Quick start

**1. Install** (from project root, pick one):

```console
uv sync                                    # uv
python -m venv .venv && pip install -e .   # pip
poetry install                             # Poetry
```

**2. Configure environment** — copy `.env.example` to `.env` and set `DATABASE_URL`, `OPENAI_API_KEY`, and DataForSEO credentials.

**3. Run:**

```console
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\Activate.ps1         # Windows
```

**4. Run migrations & app:**

```console
alembic upgrade head
flask --app app:create_app run
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/profiles` | Create a business profile |
| GET | `/api/v1/profiles/{profile_uuid}` | Get profile with summary stats |
| POST | `/api/v1/profiles/{profile_uuid}/run` | Run the 3-agent pipeline (sync) |
| GET | `/api/v1/profiles/{profile_uuid}/queries` | List discovered queries (paginated, filterable) |
| GET | `/api/v1/profiles/{profile_uuid}/recommendations` | List content recommendations |
| POST | `/api/v1/queries/{query_uuid}/recheck` | Re-run visibility scoring on one query |

### Example requests

```console
# Create a profile
curl -X POST http://localhost:5000/api/v1/profiles \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme","domain":"acme.com","industry":"SaaS","description":"Project management software","competitors":["asana.com"]}'

# Run the pipeline (may take several minutes)
curl -X POST http://localhost:5000/api/v1/profiles/{profile_uuid}/run

# Get profile with summary stats
curl http://localhost:5000/api/v1/profiles/{profile_uuid}

# List queries (filtered, paginated)
curl "http://localhost:5000/api/v1/profiles/{profile_uuid}/queries?min_score=0.5&status=not_visible&page=1&per_page=20"

# Get recommendations
curl http://localhost:5000/api/v1/profiles/{profile_uuid}/recommendations

# Recheck a single query after publishing content
curl -X POST http://localhost:5000/api/v1/queries/{query_uuid}/recheck
```

## Database Schema

Four tables power the API. Schema decisions:

| Table | Purpose |
|-------|---------|
| `business_profiles` | Core business context (domain, industry, competitors) |
| `pipeline_runs` | One row per pipeline execution; tracks status, counts, tokens |
| `discovered_queries` | Queries from Agent 1, scored by Agent 2 |
| `content_recommendations` | Content gaps from Agent 3 |

**Merged discovery + scoring in `discovered_queries`:** A single table holds both discovery fields (`query_text`, `api_keyword`, `commercial_intent`) and scoring fields (`opportunity_score`, `domain_visible`, etc.). This keeps recheck updates simple — one row to load and patch.

**`run_uuid` foreign key:** Each pipeline run appends new query and recommendation rows rather than replacing history. List endpoints scope to the **latest completed run** for a profile to avoid duplicate `query_text` entries in API responses.

**Nullable `domain_visible`:** Supports the `?status=unknown` filter for queries that have not yet been scored or have indeterminate visibility.

**Extra columns `api_keyword` and `commercial_intent`:** Required for Agent 2 recheck (DataForSEO keyword lookup) and the opportunity score formula (commercial intent multiplier).

## Pipeline

The pipeline runs synchronously in sequence:

```
Query Discovery (LLM) → Visibility Scoring (DataForSEO) → Content Recommendations (LLM)
```

Results are persisted after each run. Re-running a profile creates a new `pipeline_run` record and appends new query/recommendation rows.
