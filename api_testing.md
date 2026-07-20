# API Testing Guide

Hands-on walkthrough for exercising every endpoint and verifying all three pipeline agents against a running server at `http://127.0.0.1:5000`.

## Test run summary

| Metric | Result |
|--------|--------|
| Pipeline status | `completed` |
| Queries discovered | 19 |
| Queries scored | 1 |
| Content recommendations | 5 |
| Tokens used | 1,777 |
| Profile UUID | `c4653814-de58-4ec3-b682-7a9b170f43d5` |

> **Note:** Visibility scoring was limited to 1 query during this run (dev mode in `visibility_scoring_agent.py` to save DataForSEO credits). The remaining 18 queries stayed in `pending` status.

---

## 1. Create a profile

**Endpoint:** `POST /api/v1/profiles`

```powershell
$domain = "acme-test-$([guid]::NewGuid().ToString().Substring(0,8)).com"
$payload = @{
  name        = "Acme Test"
  domain      = $domain
  industry    = "SaaS"
  description = "Project management software"
  competitors = @("asana.com", "monday.com")
} | ConvertTo-Json

$profile = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/v1/profiles" `
  -Method POST `
  -ContentType "application/json" `
  -Body $payload

$profile | ConvertTo-Json -Depth 5
```

**Response:**

```json
{
  "created_at": "2026-07-20T05:41:47",
  "domain": "acme-test-36803ce2.com",
  "name": "Acme Test",
  "profile_uuid": "c4653814-de58-4ec3-b682-7a9b170f43d5",
  "status": "created"
}
```

---

## 2. Run the pipeline

**Endpoint:** `POST /api/v1/profiles/{uuid}/run`

Runs all three agents in sequence: Query Discovery → Visibility Scoring → Content Recommendations.

```powershell
$profileUuid = "c4653814-de58-4ec3-b682-7a9b170f43d5"

Write-Host "Running pipeline for $profileUuid ..."
$result = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/v1/profiles/$profileUuid/run" `
  -Method POST `
  -TimeoutSec 600

$result | ConvertTo-Json -Depth 8
```

**Response (highlights):**

```json
{
  "status": "completed",
  "queries_discovered_count": 19,
  "queries_scored_count": 1,
  "total_tokens_used": 1777,
  "error": null,
  "top_opportunity_queries": [
    {
      "query_text": "What are the pros and cons of using Asana?",
      "query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4",
      "domain_visible": false,
      "estimated_search_volume": 70,
      "competitive_difficulty": 56,
      "opportunity_score": 0.664,
      "visibility_reason": "DataForSEO LLM Mentions API: no Google AI Overview records found for query 'What are the pros and cons of using Asana?'."
    }
  ],
  "content_recommendations": [
    {
      "content_type": "comparison",
      "priority": "high",
      "title": "Asana vs. Competitors: Weighing the Pros and Cons",
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4"
    },
    {
      "content_type": "blog_post",
      "priority": "high",
      "title": "The Pros and Cons of Using Asana for Project Management",
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4"
    },
    {
      "content_type": "guide",
      "priority": "medium",
      "title": "Comprehensive Guide to Project Management Tools: Is Asana Right for You?",
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4"
    },
    {
      "content_type": "faq",
      "priority": "medium",
      "title": "Frequently Asked Questions About Asana: Pros and Cons",
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4"
    },
    {
      "content_type": "landing_page",
      "priority": "low",
      "title": "Discover the Advantages and Disadvantages of Asana",
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4"
    }
  ]
}
```

<details>
<summary>Full pipeline response</summary>

```json
{
  "content_recommendations": [
    {
      "content_type": "comparison",
      "priority": "high",
      "rationale": "This comparison piece will highlight the advantages and disadvantages of Asana compared to popular alternatives, addressing the query directly and providing potential customers with valuable insights.",
      "recommendation_uuid": "39fd6b6d-5524-4f67-b13b-ab55df59cd11",
      "target_keywords": ["Asana pros and cons", "Asana comparison", "Asana alternatives"],
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4",
      "title": "Asana vs. Competitors: Weighing the Pros and Cons"
    },
    {
      "content_type": "blog_post",
      "priority": "high",
      "rationale": "A dedicated blog post that explores in detail the benefits and drawbacks of using Asana, directly answering the query and enhancing the domain's authority in project management tools.",
      "recommendation_uuid": "97db524f-6406-493a-83ce-25f7d28e4f39",
      "target_keywords": ["Asana pros", "Asana cons", "project management tools"],
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4",
      "title": "The Pros and Cons of Using Asana for Project Management"
    },
    {
      "content_type": "guide",
      "priority": "medium",
      "rationale": "This guide will provide an in-depth look at various project management tools, including Asana, helping users understand where Asana excels and where it may fall short, thus addressing the visibility gap.",
      "recommendation_uuid": "b4d806f7-26f8-4a2b-bb64-3e2ab6c4c56a",
      "target_keywords": ["project management guide", "Asana review", "best project management tools"],
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4",
      "title": "Comprehensive Guide to Project Management Tools: Is Asana Right for You?"
    },
    {
      "content_type": "faq",
      "priority": "medium",
      "rationale": "An FAQ section that answers common questions about Asana's strengths and weaknesses, providing quick and concise information for users exploring their options.",
      "recommendation_uuid": "64643097-d670-40dc-a791-b8498a9cb69a",
      "target_keywords": ["Asana FAQ", "Asana pros and cons questions", "using Asana"],
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4",
      "title": "Frequently Asked Questions About Asana: Pros and Cons"
    },
    {
      "content_type": "landing_page",
      "priority": "low",
      "rationale": "A dedicated landing page focused on outlining the pros and cons of Asana, optimized for search visibility and conversions, targeting users who are in the research phase.",
      "recommendation_uuid": "6d7c91e6-6eaf-4de2-a683-375a861e82bb",
      "target_keywords": ["Asana advantages", "Asana disadvantages", "project management software pros and cons"],
      "target_query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4",
      "title": "Discover the Advantages and Disadvantages of Asana"
    }
  ],
  "error": null,
  "pipeline_run_uuid": "55dd7e52-2d00-496d-bde0-b92698726d27",
  "queries_discovered_count": 19,
  "queries_scored_count": 1,
  "status": "completed",
  "top_opportunity_queries": [
    {
      "ai_search_volume": null,
      "commercial_intent": "informational",
      "competitive_difficulty": 56,
      "difficulty_source": "google_ads",
      "discovered_at": "2026-07-20T05:44:08.166188+00:00",
      "domain_visible": false,
      "estimated_search_volume": 70,
      "opportunity_score": 0.664,
      "query_text": "What are the pros and cons of using Asana?",
      "query_uuid": "83f4aabb-f5b2-4013-b139-c8031d430ac4",
      "search_volume_source": "google_ads",
      "visibility_position": null,
      "visibility_reason": "DataForSEO LLM Mentions API: no Google AI Overview records found for query 'What are the pros and cons of using Asana?'."
    }
  ],
  "total_tokens_used": 1777
}
```

</details>

---

## 3. Inspect stored results

**Endpoints:**

- `GET /api/v1/profiles/{uuid}`
- `GET /api/v1/profiles/{uuid}/queries`
- `GET /api/v1/profiles/{uuid}/recommendations`

```powershell
$profileUuid = "c4653814-de58-4ec3-b682-7a9b170f43d5"

Write-Host "=== PROFILE ==="
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/v1/profiles/$profileUuid" |
  ConvertTo-Json -Depth 5

Write-Host "`n=== QUERIES ==="
$queries = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/v1/profiles/$profileUuid/queries?per_page=50"
Write-Host "Total queries: $($queries.total)"
$queries.items | Group-Object scoring_status | ForEach-Object {
  Write-Host "$($_.Name): $($_.Count)"
}

Write-Host "`n=== RECOMMENDATIONS ==="
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/v1/profiles/$profileUuid/recommendations" |
  ConvertTo-Json -Depth 5
```

**Profile response:**

```json
{
  "competitors": ["asana.com", "monday.com"],
  "created_at": "2026-07-20T05:41:47",
  "description": "Project management software",
  "domain": "acme-test-36803ce2.com",
  "industry": "SaaS",
  "name": "Acme Test",
  "profile_uuid": "c4653814-de58-4ec3-b682-7a9b170f43d5",
  "status": "completed",
  "summary_stats": {
    "avg_opportunity_score": 0.664,
    "total_queries_discovered": 19
  },
  "updated_at": "2026-07-20T05:44:14"
}
```

**Query scoring breakdown:**

| Status | Count |
|--------|-------|
| scored | 1 |
| pending | 18 |

**Recommendations:** 5 items linked to the not-visible query *"What are the pros and cons of using Asana?"*

---

## Agent verification checklist

| Agent | Verified by | Result |
|-------|-------------|--------|
| Query Discovery | 19 queries in profile | Pass |
| Visibility Scoring | 1 query scored with volume, difficulty, visibility | Pass |
| Content Recommendations | 5 recommendations for not-visible query | Pass |
