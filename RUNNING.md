# CodeScope — Running Locally

This guide covers how to start both the **frontend** and **backend** for local development.

## Prerequisites


| Requirement | Version    | Notes                  |
| ----------- | ---------- | ---------------------- |
| Node.js     | ≥ 20.x     | Frontend runtime       |
| Python      | ≥ 3.12     | Backend runtime        |
| pip / uv    | Latest     | Python package manager |
| Git         | Any recent | Version control        |


> **Note:** This project uses **Supabase** (cloud) for authentication and database. No local database setup is needed.

---

## Quick Start

Run both services in separate terminals:

```bash
# Terminal 1 — Backend
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8080

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000).

---

## Backend

### Setup

```bash
cd backend
```

#### Option A — uv (recommended, faster)

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8080
```

#### Option B — pip

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8080
```

### Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```


| Variable            | Required | Description                                                                                                                      |
| ------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `GITHUB_MODELS_PAT` | **Yes**  | GitHub PAT for AI explanations. Generate at [github.com/settings/tokens](https://github.com/settings/tokens) with `models` scope |
| `OLLAMA_CLOUD_URL`  | No       | Ollama endpoint (Phase 4)                                                                                                        |
| `OLLAMA_MODEL`      | No       | Ollama model name (Phase 4)                                                                                                      |
| `LOG_LEVEL`         | No       | Logging level (`DEBUG`, `INFO`, `WARNING`). Default: `INFO`                                                                      |


> ⚠️ Without `GITHUB_MODELS_PAT`, the `/api/llm/explain` endpoint will return a placeholder message instead of AI-generated explanations.

### Verify Backend is Running

```bash
curl http://localhost:8080/health
# Expected: {"status":"ok"}
```

### API Documentation

Once running, visit:

- Swagger UI: [http://localhost:8080/docs](http://localhost:8080/docs)
- ReDoc: [http://localhost:8080/redoc](http://localhost:8080/redoc)

### Running Tests

```bash
cd backend
pytest                    # All tests
pytest tests/unit/       # Unit tests only
pytest tests/integration/ # Integration tests only
pytest -v                # Verbose output
```

---

## Frontend

### Setup

```bash
cd frontend
npm install
```

### Environment Variables

The frontend uses Supabase for auth. Credentials are already configured in `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8080
NEXT_PUBLIC_SUPABASE_URL=https://cyzpvltrayvpdooxgmaj.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-anon-key>
```

> These are already set. Only change them if you're using a different Supabase project.

### Running Development Server

```bash
npm run dev
```

Opens at [http://localhost:3000](http://localhost:3000).

### Other Frontend Scripts

```bash
npm run build        # Production build
npm run start        # Start production server
npm run lint         # ESLint check
npm run type-check   # TypeScript type check
npm test             # Vitest unit tests
```

---

## E2E Tests

### Setup

E2E tests require test credentials. Create the test env file:

```bash
cd frontend
cp .env.test.example .env.test
```

Edit `.env.test` and fill in:

```env
E2E_TEST_EMAIL=your-email@example.com
E2E_TEST_PASSWORD=your-password
```

The Supabase credentials are pre-filled.

### Running Tests

```bash
cd frontend

# All tests (including auth-dependent)
npx playwright test e2e/review.spec.ts

# Only auth tests
npx playwright test --grep "@auth"

# Only login UI tests (no credentials needed)
npx playwright test --grep "Login Page UI"

# With UI (headed mode)
npx playwright test e2e/review.spec.ts --headed

# With trace on failure (for debugging)
npx playwright test e2e/review.spec.ts --trace=on
```

### Test Results


| Suite                   | Tests | Credentials Needed |
| ----------------------- | ----- | ------------------ |
| Login Page UI           | 4     | No                 |
| Sign-Up Page            | 1     | No                 |
| Authenticated Dashboard | 7     | Yes                |
| Review Flow (SM-2)      | 4     | Yes + review cards |
| Route Protection        | 3     | No                 |
| Test Environment        | 1     | No                 |


---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser                                      │
│                    http://localhost:3000                             │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Next.js Frontend                                           │   │
│   │  - React 19 + TypeScript                                   │   │
│   │  - Monaco Editor (code input)                               │   │
│   │  - Supabase Auth (login/signup)                            │   │
│   │  - SM-2 Review System                                      │   │
│   └───────────────┬─────────────────────────────────────────────┘   │
│                   │                                                  │
│                   │  POST /api/trace                                 │
│                   │  GET  /api/dashboard                             │
│                   │  GET  /api/review/:id                            │
│                   ▼                                                  │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                    http://localhost:8080
┌───────────────────────────┴───────────────────────────────────────────┐
│                    FastAPI Backend                                    │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  Routes                                                     │  │
│   │  POST /api/trace       — Parse & trace Python code          │  │
│   │  GET  /api/traces      — List user's traces                │  │
│   │  GET  /api/dashboard   — Dashboard data + due reviews      │  │
│   │  GET  /api/review/:id  — Get review card with trace        │  │
│   │  POST /api/review/:id  — Submit SM-2 rating                │  │
│   │  GET  /api/llm/explain — AI code explanation (GitHub)     │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  Tracer                                                     │  │
│   │  Python bytecode instrumentation                            │  │
│   │  AST parsing via `ast` module                               │  │
│   │  Step generation (variable states)                          │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  Supabase (cloud)                                           │  │
│   │  PostgreSQL — traces, review_cards, profiles                 │  │
│   │  Auth — user authentication                                 │  │
│   └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Frontend can't reach backend

- Ensure backend is running on port **8080**
- Check `NEXT_PUBLIC_API_URL=http://localhost:8080` in `.env.local`
- Backend CORS is configured for `localhost:3000` — won't work with a different port

### Login/signup not working

- Verify Supabase URL and anon key in `.env.local` are correct
- Check browser console for Supabase connection errors
- Ensure the user account is confirmed in Supabase

### AI explanations show placeholder

- Set `GITHUB_MODELS_PAT` in `backend/.env`
- Restart the backend after setting the variable

### Tests fail with "No E2E_TEST_EMAIL/E2E_TEST_PASSWORD"

- Create `frontend/.env.test` with valid credentials (see E2E Tests section above)
- Credentials must match an existing Supabase account

### Backend import errors

- Ensure Python ≥ 3.12 is installed
- Run `pip install -e ".[dev]"` in the backend directory
- Try `uv sync` if using uv

### Port already in use

```bash
# Find what's using port 8080
netstat -ano | findstr :8080   # Windows
lsof -i :8080                   # macOS/Linux

# Kill the process or use a different port
uvicorn app.main:app --reload --port 8081
# Then update frontend/.env.local: NEXT_PUBLIC_API_URL=http://localhost:8081
```

