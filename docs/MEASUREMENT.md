# Measurement & Observability — CogniTrace

This document explains what CogniTrace logs, where it lives, and how to
query it. It is the source of truth for anyone (researchers, operators,
thesis reviewers) who needs to answer questions like:

- "How many LLM calls did we make during the study?"
- "What was the cache-hit rate?"
- "How long did `POST /api/traces/run` take at p50 / p95?"
- "Which LLM providers were used and how often?"
- "Are we seeing any rate-limit rejections?"

If you add a new metric, document it here **in the same commit** that
adds the row.

---

## 1. What we collect

CogniTrace collects three families of telemetry:

| Family | Purpose | Lives in | Workstream |
|---|---|---|---|
| **LLM call metrics** | Per-call cost, latency, cache status, provider, model | `llm_call_metrics` | 6 |
| **Daily LLM rollups** | Aggregated per-day cache-hit rate + p50 latency | `llm_call_metrics_daily` | 6, 10 |
| **Concept categories** | Normalised tags used to cluster misconceptions | `concept_categories`, `trace_concept_tags`, `review_card_concepts` | 4 |
| **Trace review queue** | Manual grounding-check workflow for LLM explanations | `explanations` columns + `v_explanations_review_queue` view | 4 |
| **HTTP access logs** | Standard FastAPI/Starlette per-request logs | stdout / container logs | — |
| **Coverage** | pytest-cov line + branch coverage | CI artifacts | 7 |
| **Adaptive checkpoint metrics** | Which difficulty mode was selected for each `/llm/diagnose` call (T1-C) | `llm_call_metrics.checkpoint_mode` | 11 (T1-C) |
| **Fingerprint deltas** | Field-by-field comparison between two trace fingerprints (T1-D) | in-memory, not persisted | 11 (T1-D) |
| **Cognitive load events** | Pause / replay / checkpoint-miss events that feed the load dial (T1-A) | `anonymous_events` | 11 (T1-A) |
| **Cognitive load estimates** | The 0..100 score + sub-component breakdown served by `/api/load/trace/{trace_id}` (T1-A) | in-memory, recomputed per request | 11 (T1-A) |

We do **not** collect:

- User PII beyond the auth user-id (no IP, no email in logs).
- Free-form code written by the user — it lives in `traces.code`, not in metrics.
- Prompt content of successful LLM calls — only the cache-key fingerprint.

---

## 2. Schema

### `llm_call_metrics` — per-call telemetry

Added by migration `V011__llm_call_metrics.sql` (Workstream 6).

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` | Primary key |
| `created_at` | `timestamptz` | When the LLM call completed (or returned from cache) |
| `user_id` | `uuid` | Auth user (nullable for service-account traffic) |
| `trace_id` | `uuid` | The trace the call was answering (nullable for non-trace calls) |
| `provider` | `text` | One of `ollama_cloud`, `github_models`, `custom_openai` |
| `model_name` | `text` | E.g. `llama3.2`, `gpt-4o-mini` |
| `cache_hit` | `boolean` | `true` when the explanation was served from cache |
| `cache_key` | `text` | SHA-256 of (code, line, locals) — fingerprint only |
| `latency_ms` | `int` | End-to-end latency including the full streamed response |
| `input_tokens` | `int` | Provider-reported prompt tokens (nullable) |
| `output_tokens` | `int` | Provider-reported completion tokens (nullable) |
| `error` | `text` | `null` on success; error class on failure |

Indexes:
- `idx_llm_call_metrics_created_at`
- `idx_llm_call_metrics_provider`
- `idx_llm_call_metrics_user_id`
- `idx_llm_call_metrics_trace_id`

RLS: per-user (`user_id = auth.uid()`) plus a service-role bypass.

### `llm_call_metrics_daily` — daily rollup

Added by migration `V011__llm_call_metrics.sql`. Populated by an
aggregation job that runs every hour (see §5 below).

| Column | Type | Notes |
|---|---|---|
| `day` | `date` | Truncated to UTC midnight |
| `provider` | `text` | Per-provider rollup |
| `cache_hit_rate` | `numeric(5,4)` | `hits / total` for the day |
| `p50_latency_ms` | `int` | Median end-to-end latency |
| `p95_latency_ms` | `int` | p95 end-to-end latency |
| `total_calls` | `int` | Includes cache hits and misses |
| `total_input_tokens` | `bigint` | Sum across the day |
| `total_output_tokens` | `bigint` | Sum across the day |

### `explanations` grounding-check columns

Added by migration `V012__explanations_grounding_check.sql`. Used by the
manual evaluation workflow that backs our RQ2 (grounding) claim.

| Column | Type | Notes |
|---|---|---|
| `grounded` | `boolean` | Reviewer's verdict: explanation is faithful to the trace |
| `hallucination_flag` | `boolean` | Reviewer flagged a hallucination |
| `review_status` | `text` | One of `pending`, `in_review`, `reviewed`, `skipped` |
| `reviewed_at` | `timestamptz` | When the reviewer closed the row |
| `reviewer_id` | `uuid` | Auth user who reviewed it |

View: `v_explanations_review_queue` returns explanations with
`review_status = 'pending'` ordered by creation time — the queue that
backfills into our annotation tool.

### Concept categories

Added by migration `V010__concept_categories.sql`. Replaces the
denormalised `TEXT[]` tags we had in `traces.concept_tags` and
`review_cards.concept`. Lets us query "how many traces this week hit
`off_by_one`?" without `unnest()` gymnastics.

---

## 3. Where the metrics are written

Every code path lives in [`backend/app/services/llm_router.py`](../backend/app/services/llm_router.py).
The router writes one `llm_call_metrics` row per *request*, regardless of
whether the response was streamed, served from cache, or failed.

Pseudocode:

```python
async def stream_explanation(...):
    cache_text = await self._cache.get(cache_key)
    if cache_text:
        await self._record_metric(provider=None, cache_hit=True, ...)
        for chunk in stream_text(cache_text):
            yield chunk
        return
    started = time.monotonic()
    async for chunk in self._stream_provider(...):
        yield chunk
    await self._record_metric(provider=..., cache_hit=False, latency_ms=...)
```

The metric insert is **fire-and-forget**: a metric-write failure never
fails the user-facing request. The cost of one dropped metric row is
strictly less than one dropped explanation.

---

## 4. How to query

### Live queries (Supabase SQL editor or `psql`)

Last 24 hours of LLM activity, broken down by provider:

```sql
SELECT
    date_trunc('hour', created_at) AS hour,
    provider,
    COUNT(*) AS calls,
    AVG(latency_ms)::int AS avg_latency_ms,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS hits,
    ROUND(100.0 * SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) / COUNT(*), 1) AS hit_pct
FROM llm_call_metrics
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY 1, 2
ORDER BY 1 DESC;
```

Top misconceptions across all traces this week:

```sql
SELECT cc.slug, COUNT(*) AS hits
FROM trace_concept_tags tct
JOIN concept_categories cc ON cc.id = tct.category_id
JOIN traces t ON t.id = tct.trace_id
WHERE t.created_at > NOW() - INTERVAL '7 days'
GROUP BY cc.slug
ORDER BY hits DESC
LIMIT 20;
```

Pending grounding reviews:

```sql
SELECT * FROM v_explanations_review_queue LIMIT 50;
```

### Cached query: `/api/metrics/cache-hit-rate`

(Workstream 10.) Returns the last-N-day daily rollup:

```
GET /api/metrics/cache-hit-rate?window=7d
```

```json
{
  "window_days": 7,
  "rows": [
    {"day": "2026-09-17", "provider": "ollama_cloud", "cache_hit_rate": 0.42, "p50_latency_ms": 1180, "total_calls": 318},
    {"day": "2026-09-17", "provider": "github_models", "cache_hit_rate": 0.38, "p50_latency_ms": 1840, "total_calls": 92}
  ]
}
```

Window constraints: 1d ≤ window ≤ 90d. Defaults to 7d if omitted.
Rate-limited to 30 requests/minute per remote address (see
[`CONTRIBUTING.md`](../CONTRIBUTING.md) §7).

### CI / local

Coverage report:

```bash
cd backend
python -m pytest tests/unit --cov=app --cov=tracer --cov-report=term-missing
```

This is the same command that drives the CI coverage gate. Anything
that drops the threshold fails the build.

---

## 5. Aggregation job

The daily rollup `llm_call_metrics_daily` is populated by a job that runs
inside the FastAPI process. The job is registered in
[`backend/app/main.py`](../backend/app/main.py) on startup and sleeps for
an hour between runs.

For local dev you can force a refresh:

```bash
psql "$DATABASE_URL" -c "INSERT INTO llm_call_metrics_daily (...) SELECT ... FROM llm_call_metrics GROUP BY day, provider ON CONFLICT (day, provider) DO UPDATE SET ...;"
```

For production deployments, the same SQL is wrapped in a
`pg_cron`-style schedule — see your deployment's docs for how to enable
`pg_cron` on Supabase.

For local single-process deployments, the FastAPI process spins up a
background task (`app.services.metrics_aggregator.run_periodically`)
that runs the rollup every hour. See
[`backend/app/services/metrics_aggregator.py`](../backend/app/services/metrics_aggregator.py).

---

## 9. Database backups

The Postgres database should be backed up daily. The simplest tool is
the [`scripts/backup_db.sh`](../backend/scripts/backup_db.sh) script:

```bash
cd backend
DATABASE_URL='postgres://user:pass@host:5432/db' ./scripts/backup_db.sh
```

It produces a timestamped `cognitrace_<date>.sql.gz` file under
`./backups/` and prunes anything older than `${RETENTION_DAYS}` (default
14 days). Wire it into cron:

```cron
30 2 * * * cd /app && DATABASE_URL='...' ./scripts/backup_db.sh >> /var/log/cognitrace/backup.log 2>&1
```

For off-host durability, sync the resulting gzip to S3 / rclone / your
favourite object store. The local file is only the first hop.

---

## 6. What "looks healthy" looks like

These are the ballpark numbers we target under the empirical study
workload (≈ 50 users × 30 traces / week):

| Metric | Healthy | Investigate |
|---|---|---|
| Cache hit rate | > 30% | < 15% — likely the cache key isn't matching as expected |
| p50 latency | < 2s | > 4s — provider is slow or network is congested |
| p95 latency | < 6s | > 10s — one user is hammering or provider is rate-limiting us |
| Error rate | < 1% | > 5% — check the provider status page first |
| Hallucination flag rate | < 10% | > 25% — grounding regression, check the prompt template |

These are starting points, not hard SLAs. Adjust them after the pilot
with real numbers.

---

## 7. Adding a new metric

1. Add the column to `llm_call_metrics` via a new `V013__….sql` migration.
2. Insert the row from the appropriate call site in `llm_router.py`
   using the `_record_metric` helper. Do **not** `await` it from a
   streaming path unless you accept the latency.
3. Add the column to this table in §2.
4. If the metric should be queryable from the dashboard, add a column to
   `llm_call_metrics_daily` and update the aggregation SQL.
5. Update §6 if it changes what "healthy" means.

If you skip steps 3-5, the metric will be silently dropped from every
query the next person writes. Don't skip them.

---

## 8. Related docs

- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — where the metric writes
  fit in the request lifecycle.
- [`docs/SECURITY-SANDBOX.md`](SECURITY-SANDBOX.md) — sandbox logs are
  intentionally *not* in `llm_call_metrics`; they live in container logs.
- [`docs/THESIS-02-CONTRIBUTIONS.md`](THESIS-02-CONTRIBUTIONS.md) — how
  the metrics back the empirical claims.

---

## 9. T1-C: Adaptive Checkpoint Difficulty

### What's collected

The `llm_call_metrics` table grows a new `checkpoint_mode` column
(migration `V017__checkpoint_mode.sql`, Workstream 11 / T1-C). Every
diagnose call records which of the three difficulty modes the selector
chose.

| Column | Type | Notes |
|---|---|---|
| `checkpoint_mode` | `text` | One of `direct`, `scaffolded`, `contrastive`, or `NULL` |

Partial index `idx_llm_call_metrics_checkpoint_mode` covers queries of
the form "how often did we pick contrastive mode last week?".

### What the modes mean

| Mode | When it's picked | What the system prompt changes |
|---|---|---|
| `direct` | No recent misses, OR the student has hit ≥ 80% mastery. | Standard misconception diagnosis, no hint. |
| `scaffolded` | The student missed this concept in the last 24h. | Adds an inline `hint` field with a targeted cue. |
| `contrastive` | Two misses in the last 72h, mastery < 50%. | Adds a `hint` field that asks the student to imagine a counterfactual. |

### Decision rubric

[`backend/app/services/checkpoint_selector.py`](../backend/app/services/checkpoint_selector.py)
implements the rubric. The function is pure (no DB, no LLM) and is
covered by unit tests. Inputs:

- `concept_tag`: SM-2 concept tag (or None → direct).
- `recent_review_events`: 30-day window of `review_events` for the user + tag.

The selector also honours `override_mode: true` from the client, which
forces the requested mode and is what the "Show hint" button uses to
re-fetch a diagnosis *with* the hint field populated.

### Sample queries

Hit-rate of each mode over the last week:

```sql
SELECT checkpoint_mode, COUNT(*) AS calls
FROM llm_call_metrics
WHERE created_at > NOW() - INTERVAL '7 days'
  AND checkpoint_mode IS NOT NULL
GROUP BY 1
ORDER BY calls DESC;
```

Cache-hit rate per mode (does scaffolding hurt cache reuse?):

```sql
SELECT checkpoint_mode,
       ROUND(100.0 * SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) / COUNT(*), 1) AS hit_pct
FROM llm_call_metrics
WHERE created_at > NOW() - INTERVAL '7 days'
  AND checkpoint_mode IS NOT NULL
GROUP BY 1
ORDER BY checkpoint_mode;
```

### What "looks healthy" looks like (additions to §6)

| Metric | Healthy | Investigate |
|---|---|---|
| Share of calls in `contrastive` mode | < 15% | > 40% — the selector is over-rewarding struggle |
| Latency p50 for `scaffolded` vs `direct` | within ±15% | > 2× — the scaffolded prompt is too long |
| `hint` field populated when `selectedMode != direct` | 100% | < 95% — the prompt template dropped the hint branch |

---

## 10. T1-A: Cognitive Load Dashboard

### What's collected

The dashboard consumes three sources, none of which require new
database tables:

1. **`traces.steps`** — the saved Python trace events. Used for the
   *structural* sub-score (branches, loop iterations, recursion,
   exception events, peak live-variable count).
2. **`anonymous_events`** — client-emitted, *unauthenticated* events.
   Tagged with a `trace_id` in the metadata. Used for the *interaction*
   sub-score (pauses ≥ 2 s, What-If replays, checkpoint misses).
3. **`review_events`** — SM-2 review history for the calling user +
   primary concept tag of the trace, last 30 days. Used for the *SM-2*
   sub-score (inverse of mastery rating).

The output is the `LoadEstimate` dataclass in
[`backend/app/services/load_estimator.py`](../backend/app/services/load_estimator.py)
plus a chronological `series` of `LoadPoint`s for the chart.

### Endpoint

```
GET /api/load/trace/{trace_id}
```

Response shape (200):

```json
{
  "trace_id": "…",
  "score": 67,
  "structural": 0.53,
  "interaction": 1.0,
  "sm2": 0.5,
  "series": [
    {"t_seconds": 0.05, "score": 0, "label": "branch/loop entry (if)"},
    {"t_seconds": 0.105, "score": 0, "label": "exception (exception)"}
  ],
  "notes": ["student paused or replayed frequently", "1 long pauses (≥8s)"],
  "primary_concept_tag": "FUNCTION",
  "events_count": {
    "trace_steps": 14,
    "interaction_events": 3,
    "sm2_events": 4
  }
}
```

401 if no Bearer token (we need the caller's profile id to resolve
SM-2). 404 if the trace doesn't exist.

### Frontend event vocabulary

[`frontend/lib/analytics.ts::trackLoadEvent`](../frontend/lib/analytics.ts)
ships four stable event names — changing any of them is a breaking
measurement-side change:

| `event_type` | Emitted from | Metadata |
|---|---|---|
| `tracer_pause` | Tracer page when `selectedLine` is stable ≥ 2 s | `{ trace_id, line, duration_ms: 2000 }` |
| `tracer_resume` | (reserved, currently unused) | `{ trace_id, line }` |
| `tracer_whatif_replay` | Tracer page "What If?" button click | `{ trace_id }` |
| `tutor_checkpoint_miss` | TutorChallenge submit handler when `correct === false` | `{ trace_id, concept_tag }` |

The legacy strings (`what_if_replay`, `tutor_checkpoint_submitted`) are
still recognised by the estimator for backward compatibility with
telemetry ingested before T1-A shipped.

### Methodology footnote

The 0..100 score is a *proxy*, not a Sweller-style cognitive-load
measurement. It is designed to *covary* with effort so the H1
mediator analysis has a usable signal — we do **not** claim that the
score has the same units as a NASA-TLX panel. Calibration will be
re-validated against the pilot study's `cognitrace_diary_v1` Likert
ratings once those are available (planned for `THESIS-W3`).

The combine weights are `structural=0.55, interaction=0.30, sm2=0.15`.
Structural dominates because it is the most objective signal (derived
from the trace itself, not from student behaviour that can be noisy).
Re-calibrate the weights if the pilot study shows the diary ratings
correlate more strongly with a different mix.

### Sample queries

What was the average load score per concept tag last week?

```sql
-- The estimator doesn't write to the DB; this query is run over
-- trace_concept_tags joined to traces; the score is recomputed on
-- demand by the endpoint.
SELECT tct.category_id, COUNT(*) AS trace_count
FROM trace_concept_tags tct
JOIN traces t ON t.id = tct.trace_id
WHERE t.created_at > NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY trace_count DESC;
```

Distribution of pauses per trace:

```sql
SELECT metadata->>'trace_id' AS trace_id,
       COUNT(*) AS pauses
FROM anonymous_events
WHERE event_type IN ('tracer_pause', 'tracer_whatif_replay', 'tutor_checkpoint_miss')
  AND occurred_at > NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY pauses DESC
LIMIT 20;
```

### What "looks healthy" looks like (additions to §6)

| Metric | Healthy | Investigate |
|---|---|---|
| Median trace load score | 30–45 | > 60 — the cohort is overloaded; revisit scaffolding |
| Share of traces with `score >= 80` | < 10% | > 25% — usability problem, not a learning problem |
| Endpoint p95 latency | < 300 ms | > 1 s — the SM-2 fetch is blocking on a slow PostgREST path |

---

## 11. T1-D: Fingerprint Comparison / Trace Diff

### What's collected

T1-D produces a *derived* artefact — there is no new persistent
column. The diff is computed on demand from two existing fingerprints
(already persisted in `trace_fingerprints` via migration
`V014__trace_fingerprints.sql`). Each delta carries the field name, the
two values, a human-readable narrative, and a `significant` boolean so
the UI can collapse cosmetic differences.

### Endpoint

```
GET /api/diff/fingerprint?a=<trace_id|share_token>&b=<trace_id|share_token>
GET /api/fingerprint/diff/card.svg?a=…&b=…   # OG-card SVG
POST /api/fingerprint/from-code               # compute without persisting
```

Both inputs are accepted as either a `trace_id` or a `share_token`. The
router disambiguates by inspecting the value (32-char hex without
dashes → token, UUID-with-dashes → trace_id).

Response (200):

```json
{
  "a": { /* FingerprintPayload */ },
  "b": { /* FingerprintPayload */ },
  "a_kind": "share_token",
  "b_kind": "trace_id",
  "deltas": [
    {
      "field": "branches",
      "label": "Branch count",
      "a_value": 2,
      "b_value": 5,
      "narrative": "Trace B has 3 more branches than Trace A.",
      "significant": true
    }
  ],
  "summary": "Trace A vs Trace B — 3 structural differences",
  "identical": false
}
```

### Frontend wiring

- [`frontend/app/tracer/compare/page.tsx`](../frontend/app/tracer/compare/page.tsx)
  is the entry point. It supports trace-id, share-token, and pasted-
  code modes (pasted code calls `POST /api/fingerprint/from-code` so the
  diff works against an ephemeral, unpersisted fingerprint).
- [`frontend/hooks/useFingerprintDiff.ts`](../frontend/hooks/useFingerprintDiff.ts)
  fetches and caches the diff, returns `{ data, loading, error }`.
- [`frontend/components/tracer/FingerprintDiff.tsx`](../frontend/components/tracer/FingerprintDiff.tsx)
  renders the side-by-side badge + delta list.
- The OG card (`/api/fingerprint/diff/card.svg`) is wired into the
  `<head>` of the compare page as `og:image` so shareable links show
  the diff inline.

### "Significant" delta semantics

A delta is flagged `significant: true` when:

- The absolute difference in a count field is ≥ 2 (e.g., 3 extra
  branches, 4 extra loop iterations).
- The two fingerprints disagree on a *categorical* field (e.g.,
  `has_recursion` flips, `error_category` changes).
- Any field where the narrative mentions "fundamentally".

Cosmetic differences (1 extra branch, identical recursion flag, etc.)
are flagged `significant: false` so the UI can collapse them by default.

### Sample queries

The most-comparable fingerprint pairs last week (by field count):

```sql
SELECT a.fingerprint->>'id' AS a_id,
       b.fingerprint->>'id' AS b_id,
       jsonb_array_length(a.fingerprint->'family_stats') AS a_size,
       jsonb_array_length(b.fingerprint->'family_stats') AS b_size
FROM trace_fingerprints a
JOIN trace_fingerprints b
  ON a.user_id = b.user_id
 AND a.trace_id <> b.trace_id
 AND abs(jsonb_array_length(a.fingerprint->'family_stats')
       - jsonb_array_length(b.fingerprint->'family_stats')) <= 2
WHERE a.created_at > NOW() - INTERVAL '7 days'
ORDER BY a.user_id
LIMIT 50;
```

### What "looks healthy" looks like (additions to §6)

| Metric | Healthy | Investigate |
|---|---|---|
| `/api/diff/fingerprint` p95 latency | < 200 ms | > 800 ms — the SVG render is dominating; cache the JSON |
| Share-token → fingerprint lookup hit-rate | > 90% | < 70% — `trace_fingerprints.share_token` index is missing |
| "Identical" rate for cross-version diffs (What-If → original) | 0% (always expected to differ) | > 20% — the What-If replay is dropping user changes |

