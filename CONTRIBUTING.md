# Contributing to CogniTrace

This is the dev-loop reference for working on CogniTrace. Read it before
opening your first PR — most of the friction you'll otherwise hit is
documented here.

---

## 1. The 30-second version

```bash
# 1. Clone and bootstrap
git clone <repo>
cd CogniTrace-AI-Tutor-for-AI-Assisted-Coding

# 2. Start the stack (Postgres, Redis, backend, frontend)
docker compose up -d

# 3. Run the migrations
cd backend
python -m alembic upgrade head   # or whatever the project uses
cd ..

# 4. Run the tests
cd backend && python -m pytest tests/unit
cd ../frontend && npm test
```

If `docker compose up` fails, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
and the README for the full bootstrap.

---

## 2. Repository layout

```
CogniTrace-AI-Tutor-for-AI-Assisted-Coding/
├── backend/
│   ├── app/
│   │   ├── routers/        FastAPI endpoints (one file per concern)
│   │   ├── services/       Stateless business logic
│   │   ├── concurrency.py  Per-process concurrency limit
│   │   └── main.py         App composition root
│   ├── tracer/             Sandboxed Python AST + dynamic tracer
│   ├── migrations/         Flyway-style SQL migrations
│   └── tests/
│       ├── unit/           Fast, no-network tests
│       └── integration/    Tests that hit the real DB / Redis
├── frontend/
│   ├── app/                Next.js App Router pages
│   ├── components/         Shared UI components
│   ├── hooks/              React hooks (the only stateful place)
│   └── lib/                API client + small utilities
├── docs/                   You are here.
└── docker-compose.yml
```

Each module file gets a 3-5 line docstring at the top:

> **purpose**: what this module is responsible for
> **collaborators**: what other modules it depends on
> **last significant change**: when it was last meaningfully edited

If you add a new module, write the docstring first. The test of a good
docstring is "could a new contributor pick up this file and know what
*not* to put in it?"

---

## 3. Development workflow

1. Create a branch from `main`: `git switch -c feat/<short-name>`.
2. Make focused commits. One logical change per commit.
3. Run the affected tests before pushing:
   ```bash
   cd backend && python -m pytest tests/unit -k <module_under_test>
   cd ../frontend && npm test -- <component_under_test>
   ```
4. Open a PR. The CI pipeline runs the full test matrix and the coverage gate.

CI must be green before merge. PRs that drop coverage below the
threshold fail the build.

---

## 4. How to add a route

1. **Identify the right router file** under `backend/app/routers/`.
   - Trace execution → `traces.py` (via `trace_executor.execute_trace_or_raise`).
   - Save / list → `traces_save.py`.
   - Share / fork → `traces_share.py`.
   - Dashboard → `dashboard.py`.
   - LLM explanation → `llm_router.py`.
   - Anything new → create a new file.

2. **Write the endpoint.** Pattern:

   ```python
   from fastapi import APIRouter, Depends, HTTPException
   from app.services.errors import auth_required_401, upstream_failure_502
   from app.deps import get_current_user

   router = APIRouter(prefix="/api/widgets", tags=["widgets"])

   @router.get("/")
   async def list_widgets(user=Depends(get_current_user)):
       ...
   ```

3. **Register the router** in [`backend/app/main.py`](backend/app/main.py):
   ```python
   from app.routers import widgets
   app.include_router(widgets.router)
   ```

4. **Add a rate-limit decorator** if the endpoint accepts user input or
   costs server resources (see §7).

5. **Write a unit test** under `backend/tests/unit/` that hits the
   router through `httpx.AsyncClient` with the dependency overrides.

6. **Update the API docs.** The OpenAPI schema auto-generates from
   FastAPI; if the response shape is non-trivial, document it inline.

---

## 5. How to add a migration

1. Create `backend/migrations/V<next-number>__<short-name>.sql`. Use
   snake_case. The number is **next** in the existing sequence — don't
   try to backfill gaps.

2. The migration is **idempotent**:
   ```sql
   CREATE TABLE IF NOT EXISTS my_new_table (...);
   CREATE INDEX IF NOT EXISTS idx_my_new_table_created_at ON my_new_table(created_at);
   ```

3. Add any new tables to the RLS policy sweep:
   ```sql
   ALTER TABLE my_new_table ENABLE ROW LEVEL SECURITY;
   CREATE POLICY "user sees own rows" ON my_new_table
     FOR SELECT USING (user_id = auth.uid());
   ```

4. Update [`backend/migrations/README.md`](backend/migrations/README.md)
   if the new migration introduces a new pattern.

5. Apply locally and verify:
   ```bash
   psql "$DATABASE_URL" -f backend/migrations/V<num>__<name>.sql
   ```

6. The CI pipeline runs every migration from scratch on a fresh
   container — if your migration fails idempotency, CI will catch it.

---

## 6. How to add a metric

See [`docs/MEASUREMENT.md`](docs/MEASUREMENT.md) §7 for the full list.
The short version:

1. Add the column to `llm_call_metrics` via migration.
2. Insert the row via `await self._record_metric(...)` in
   `llm_router.py` (or wherever the event happens).
3. Update the docs — don't skip this step.
4. If it's dashboard-worthy, also update `llm_call_metrics_daily`.

---

## 7. Rate limiting

CogniTrace uses a per-process token bucket. The decorator lives in
[`backend/app/rate_limit.py`](backend/app/rate_limit.py).

```python
from app.rate_limit import _rate_limit

@router.post("/traces")
@_rate_limit("20/minute")
async def save_trace(...):
    ...
```

When to add a decorator:
- Any endpoint that **writes** something the user controls.
- Any endpoint that **calls an LLM provider** (`@_rate_limit("10/minute")`).
- Any endpoint that hits Supabase with a non-trivial query.

When **not** to add a decorator:
- Static `/healthz`, `/readyz`, `/openapi.json`.
- Auth callbacks that already rate-limit upstream.

---

## 8. Frontend conventions

- **Stateful logic** lives in `frontend/hooks/`. Page components should
  compose hooks, not hold their own `useState` / `useEffect` chains.
- **Stateless UI** lives in `frontend/components/`.
- **API calls** go through `frontend/lib/api.ts` — never `fetch()` in a
  component.
- **Forms** are uncontrolled. Reach for a controlled component only
  when you need live validation feedback.

Style:
- Prettier (already configured).
- ESLint with the project ruleset.
- React Compiler is enabled — don't fight it with manual `useMemo`.

---

## 9. Testing

### Backend

```bash
cd backend
python -m pytest tests/unit                                     # fast loop
python -m pytest --cov=app --cov=tracer tests/unit              # with coverage
python -m pytest tests/integration -m "not slow"                 # integration
```

Coverage gate: see `.github/workflows/ci.yml` for the current
threshold. PRs that drop coverage fail the build.

### Frontend

```bash
cd frontend
npm test                       # Vitest unit tests
npm run test:e2e               # Playwright smoke
npm run typecheck              # tsc --noEmit
```

### Manual smoke

The fastest end-to-end check:

```bash
docker compose up -d
# Open http://localhost:3000
# Type `x = 1\ny = x + 1` in the editor
# Click "Run"
# Verify the trace appears and the explanation streams
```

---

## 10. Code style

- **Python**: `ruff format` + `ruff check` (replaces Black + isort + flake8).
- **TypeScript**: Prettier (already configured).
- **Type hints**: Use PEP 604 unions (`int | None`), not `Optional[int]`.
  The `UP006` rule enforces this; CI runs `ruff check --select UP --fix`.

Pre-commit:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 11. Where to ask questions

- **Architecture**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Sandbox model**: [`docs/SECURITY-SANDBOX.md`](docs/SECURITY-SANDBOX.md)
- **Research framing**: [`docs/THESIS-00-ABSTRACT.md`](docs/THESIS-00-ABSTRACT.md)
- **Metrics / observability**: [`docs/MEASUREMENT.md`](docs/MEASUREMENT.md)
- **Bug or feature request**: open an issue

If something in this document is wrong, please open a PR — this is a
living reference.
