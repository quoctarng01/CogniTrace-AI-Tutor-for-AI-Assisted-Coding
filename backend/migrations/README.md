# CogniTrace Database Migrations

Numbered SQL migrations applied in lexical order. Apply with `npx supabase db push` or your migration runner of choice.

## Order of application

| Migration | Purpose |
|---|---|
| V001 | Initial schema: profiles, traces, review_cards, explanations |
| V002 | Examples table |
| V003 | Examples seed data |
| V004 | Explanation ratings |
| V005 | Anonymous events |
| V006 | Fix RLS policies |
| V007 | Optimize RLS policies with `EXISTS` |
| V008 | Add GitHub Models PAT to profiles |
| V009 | Add custom OpenAI endpoint to profiles |
| V010 | **Concept categories** (Workstream 4). Single source of truth for `concept_tags`. |
| V011 | **LLM call metrics** (Workstream 4 + 6). `llm_call_metrics`, `llm_call_metrics_daily`, `v_llm_metrics_summary` view. |
| V012 | **Explanations grounding-check** (Workstream 4). `grounded`, `hallucination_flag`, `review_status` columns for the RQ1 manual evaluation protocol. |
| V013 | **Study sessions** (W1 pilot). `study_sessions` table + nullable `study_session_id` FK on `llm_call_metrics` and `explanations`. The frontend sends `X-Study-Session: <uuid>` on each request; backend threads it through `app.services.study_session`. Zero-cost for non-pilot traffic. |
| V014 | **Trace fingerprints** (Workstream 12 / thesis Contribution #4). `trace_fingerprints` table — deterministic visual signature for every saved trace, populated lazily on first access by `app.services.fingerprint.compute_fingerprint`. Backs `/api/traces/{id}/fingerprint`, `/fingerprint/{token}/card.svg`, and the `/fingerprint/{token}` share page. |

## Adding a new migration

1. Determine the next number (e.g. `V013`).
2. Create `backend/migrations/V013__short_description.sql`.
3. Follow the existing style: a top header comment block, idempotent statements (`CREATE … IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`), and explicit `ALTER TABLE … ENABLE ROW LEVEL SECURITY` if the table is new.
4. Backfills must use `INSERT … WHERE NOT EXISTS` to be re-runnable.
5. Add a row to the table above.

## Rolling back

There are no down-migrations. To roll back, write a new migration that reverses the previous one. This is intentional — the migrations run in production only after the RQ1 study data is collected, and we want a complete audit trail.

## Production deployment order

Apply all migrations in lexical order against the production Supabase project before any code changes that depend on them. The application is forward-compatible — it falls back to the legacy `concept_tags TEXT[]` column when the new join table is empty, so the code can ship before the migrations run.

## Local development

```bash
# Apply all migrations to local Supabase
npx supabase db reset           # full reset + apply
npx supabase db push            # apply pending migrations only
```

## Tests

The `llm_call_metrics` and `concept_categories` tables are tested by:

- `backend/tests/integration/test_dashboard.py` (existing — exercises the dashboard widget that reads from `llm_call_metrics_daily`).
- The new unit tests for the LLM router (Workstream 6) assert that a row is written to `llm_call_metrics` on every cache miss.
