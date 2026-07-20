# AI Visibility API
---

## Requirements

- [Docker](https://www.docker.com/)
- [uv](https://docs.astral.sh/uv/) for Python packages

## Quick start

### Docker

```console
cp .env.example .env   # set OPENAI_API_KEY, DataForSEO creds, POSTGRES_*
docker compose up -d --build
```

- API: http://localhost:5000
- Adminer: http://localhost:8080

### Local

```console
uv sync
cp .env.example .env
alembic upgrade head
flask --app app:create_app run
```

---

## API Testing Guide

Step-by-step PowerShell commands and sample JSON responses from a full end-to-end run (Query Discovery → Visibility Scoring → Content Recommendations).

**[View API testing guide →](api_testing.md)**

| Step | What it verifies |
|------|------------------|
| Create profile | `POST /api/v1/profiles` |
| Run pipeline | All three agents execute successfully |
| Fetch results | Profile stats, queries, and recommendations |

---
## Project Structure

The application follows a service-based architecture.

- **Routes** handle HTTP requests.
- **Services** contain the business logic.
- **Agents** implement the AI workflow using LangGraph.

When `POST /profiles/{uuid}/run` is called:

1. Any existing queries, recommendations, and run records for that profile are cleared.
2. A new pipeline run is created and the LangGraph workflow executes.
3. Results are stored in the database.

Each profile holds one current snapshot. Re-running replaces the previous data rather than keeping history.

---

## Pipeline

The workflow consists of three sequential agents.

### 1. Query Discovery

Uses OpenAI to generate 10–20 realistic AI search queries based on:

- Business domain
- Industry
- Competitors

Each query includes:

- AI search query
- API-friendly keyword
- Commercial intent

---

### 2. Visibility Scoring

Uses **DataForSEO** (no LLM involved) to:

- Check whether the domain appears in AI search citations
- Retrieve keyword volume
- Retrieve keyword difficulty
- Calculate an opportunity score

Each query is processed independently, so one failed request never stops the entire pipeline.

---

### 3. Content Recommendations

Uses OpenAI to analyze queries where the business is **not visible** and generates actionable content ideas such as:

- Blog posts
- Landing pages
- FAQs
- Comparison pages

Recommendations are linked directly to the queries they target.

---
## Error Handling

DataForSEO requests can occasionally fail due to rate limits, missing keyword data, or temporary API issues.

Instead of failing the entire pipeline:

- Failed queries are saved with `scoring_status = failed`
- Error messages are stored for debugging
- Successful queries continue processing
- The pipeline still completes successfully

Each failed query can later be rescored using:

```http
POST /queries/{uuid}/recheck
```

Only failures in the OpenAI discovery or recommendation stages cause the pipeline run to be marked as **failed**.

---

## Opportunity Score

The opportunity score ranks queries that are most valuable for creating new content.

```text
normalized_volume = volume / max_volume_in_run
normalized_ease   = 1 - (difficulty / 100)
visibility_gap    = 0.3 if domain_visible else 1.0
intent_multiplier = 1.2 (comparison)
                  | 1.15 (best_of)
                  | 1.0 (informational)

score =
((normalized_volume × 0.4) +
(normalized_ease × 0.6))
× visibility_gap
× intent_multiplier

Maximum score = 1.0
```

Keyword volume is taken from Google Ads whenever available, with DataForSEO AI search volume used as a fallback.

---
## Database

The project uses four tables:

- `business_profiles`
- `pipeline_runs`
- `discovered_queries`
- `content_recommendations`

Discovery and scoring data are intentionally stored in the same query record, making rescoring simple without additional joins.

Each query stores:

- Visibility status
- Opportunity score
- Scoring status
- Error message (if any)

Re-running the pipeline replaces the profile's previous queries and recommendations. The `pipeline_runs` table still records execution metadata (status, token count, timing) for the current run.

---

## API Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/profiles` | Create a business profile |
| GET | `/api/v1/profiles/{uuid}` | Get profile with summary stats |
| POST | `/api/v1/profiles/{uuid}/run` | Execute the complete pipeline |
| GET | `/api/v1/profiles/{uuid}/queries` | List discovered queries with filters |
| GET | `/api/v1/profiles/{uuid}/recommendations` | Get content recommendations |
| POST | `/api/v1/queries/{uuid}/recheck` | Re-score a single query |

---

## Example Usage

```bash
# Create a profile
curl -X POST http://localhost:5000/api/v1/profiles \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Acme",
    "domain":"acme.com",
    "industry":"SaaS",
    "description":"Project management software",
    "competitors":["asana.com"]
  }'

# Run the pipeline
curl -X POST http://localhost:5000/api/v1/profiles/{profile_uuid}/run

# View profile summary
curl http://localhost:5000/api/v1/profiles/{profile_uuid}

# Get visibility gaps
curl "http://localhost:5000/api/v1/profiles/{profile_uuid}/queries?status=not_visible&min_score=0.5"

# Re-score a failed query
curl -X POST http://localhost:5000/api/v1/queries/{query_uuid}/recheck
```

---
## Notes

- Re-running the pipeline replaces prior query and recommendation data for that profile.
- Individual query failures do not stop the pipeline.
- Failed queries can be rescored at any time.
- Recommendations are generated only for queries where the domain is not visible.
