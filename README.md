# CodeScope

> Real-time execution tracer for AI-generated Python code — see exactly what your code does, which branches fire, and why.

[CI](https://github.com/yourusername/codescope/actions/workflows/ci.yml)
[License: MIT](https://opensource.org/licenses/MIT)

---

## What is CodeScope?

CodeScope solves the **AI code comprehension gap** — the gap between what developers can generate with AI tools (GitHub Copilot, Cursor, Claude Code) and what they actually understand about that code.

When you paste AI-generated Python into CodeScope, you get:

- **Step-by-step execution** with variable state that updates in real time
- **Branch detection** — see exactly which `if`/`else` branch fired and which loop iteration you're on
- **"Why is this here?"** — LLM-powered explanations grounded in the actual execution context
- **Spaced repetition review** — so understanding doesn't fade after the first "aha!" moment

---

## Quick Start

### Run with Docker (recommended)

```bash
git clone https://github.com/yourusername/codescope.git
cd codescope
docker compose up --build

# Open http://localhost:3000
# API docs: http://localhost:8000/docs
```

### Run locally

**Backend:**

```bash
cd backend
cp .env.example .env
# Fill in SUPABASE_URL, REDIS_URL in .env
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
# Open http://localhost:3000
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js on Vercel)             │
│  Monaco Editor │ Variable Panel │ Animation Controls │ SSE   │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────▼────────────────────────────────┐
│                   Backend (FastAPI on Railway)              │
│  /api/traces/run → Tracer subprocess                       │
│  /api/llm/explain/stream → Ollama Cloud → Claude fallback  │
│  /api/review/* → Spaced repetition (SM-2)                  │
└────────────────────────────┬────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
  ┌──────────┐      ┌──────────────┐    ┌────────────┐
  │ Supabase │      │ Redis        │    │ Ollama     │
  │ (Postgres│      │ (Rate limit) │    │ Cloud      │
  │ + Auth)  │      └──────────────┘    └────────────┘
  └──────────┘
```

### Key Engineering Decisions

**1. Subprocess isolation for code execution**

User code runs as an **isolated Python subprocess** spawned by FastAPI per request. The subprocess:

- Executes with `sys.settrace()` active for bytecode-level instrumentation
- Is killed after 5 seconds or 500 steps (loop protection)
- Does **not** share memory with the FastAPI process
- Has `resource.setrlimit()` applied on Linux for CPU/memory limits

This is fundamentally safer than browser-side execution (Pyodide) and more controllable than a shared interpreter.

**2. Branch detection via bytecode analysis**

Most Python execution tracers show which lines executed. CodeScope goes further — it analyzes CPython bytecode to detect:

- **Conditional branches**: Which `if`/`else` branch fired and why
- **Loop iterations**: Which iteration of a `for`/`while` loop is running
- **Boolean short-circuits**: When `and`/`or` short-circuits evaluation

This is the single most impactful feature for understanding AI-generated code, where nested conditionals are often the source of confusion.

```python
# CodeScope shows:
# Step 5: if user.get('verified') and not user.get('banned'):
#   → branch: if (taken=True)
#   → iteration: 1
# Step 6: grant_access()
#   → variables: {user: {...}, verified: True, banned: False}
```

**3. Three-tier LLM routing with content-addressable caching**

The explanation engine tries LLM providers in order:

1. **Ollama Cloud** (free, no setup) — primary
2. **Local Ollama** (localhost:11434) — privacy mode
3. **Claude Sonnet 4** — fallback when others fail

Before any API call, a SHA-256 cache key is computed from `(code[:200] + line_number + line_content[:50])`. Identical requests return instantly from the database at zero cost.

**4. Redis-backed distributed rate limiting**

The rate limiter uses Redis with a Lua script for atomic read-modify-write. This works correctly across all Railway instances — a user cannot bypass the limit by hitting different instances.

---

## Project Structure

```
codescope/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point + CORS
│   │   ├── config.py         # All settings from env vars
│   │   ├── concurrency.py    # asyncio.Semaphore for concurrency
│   │   ├── routers/          # /api/traces, /llm, /review, /profiles
│   │   └── services/         # llm_router, rate_limit, tracer_runner
│   ├── tracer/               # pip-installable bytecode tracer library
│   │   ├── tracer.py         # sys.settrace() instrumentation + branch detection
│   │   ├── validator.py      # Side-effect pattern detection
│   │   └── models.py         # TraceStep dataclasses
│   ├── migrations/           # Supabase SQL migrations
│   └── tests/               # pytest + pytest-asyncio
├── frontend/
│   ├── app/
│   │   ├── page.tsx          # Landing page
│   │   ├── tracer/           # Main tracer tool
│   │   └── dashboard/         # Saved traces + review queue
│   ├── components/
│   │   ├── editor/           # Monaco wrapper
│   │   ├── tracer/           # VariablePanel, AnimationControls
│   │   ├── llm/              # ExplanationPanel (SSE streaming)
│   │   └── errors/           # React Error Boundaries
│   ├── hooks/
│   │   ├── useTrace.ts       # rAF-based animation loop
│   │   └── useStreamingExplanation.ts  # SSE with retry
│   ├── lib/
│   │   ├── api.ts            # Typed fetch wrappers
│   │   └── sm2.ts            # SM-2 spaced repetition
│   └── i18n/                 # English + Vietnamese translations
├── docker-compose.yml         # Full local dev (Supabase + Redis + FastAPI)
└── README.md
```

---

## Features

### Core

- Step-by-step Python execution via `sys.settrace()`
- Variable state tracking with type badges and change detection
- Branch decision detection (if/else/for/while)
- 5-second timeout + 500-step limit
- Side-effect validation (blocks dangerous patterns before execution)
- Monaco editor with line highlighting

### Animation

- `requestAnimationFrame`-based playback (not `setInterval`)
- Play/Pause/Step Forward/Step Backward
- Variable speed (0.5×, 1×, 2×, 5×)
- Keyboard shortcuts (Space, Arrow keys, Home/End)
- Tab visibility handling (pauses when tab is hidden)
- Step-accurate timing regardless of focus state

### LLM Explanations

- Ollama Cloud (free, primary)
- Local Ollama (localhost:11434, privacy mode)
- Claude Sonnet 4 (fallback)
- SSE streaming with token-by-token rendering
- SHA-256 content-addressable cache
- Auto-retry with exponential backoff
- Rate limiting (20/hour anonymous, unlimited Pro)

### Spaced Repetition

- SM-2 algorithm implementation
- Review queue with streak tracking
- Rating buttons: Again / Hard / Good / Easy

### Infrastructure

- Docker Compose for local dev (Supabase + Redis + FastAPI)
- Redis-backed distributed rate limiting (Lua script)
- React Error Boundaries (per-panel isolation)
- i18n (English + Vietnamese)
- Supabase Auth (email/password)
- Structured logging (structlog)
- Railway deployment configs

---

## Development

### Running Tests

```bash
cd backend
pip install -e ".[dev]"
pytest tests/ -v --cov=tracer --cov=app

cd frontend
npm install
npm test
```

### Running Tracer Tests Directly

```bash
cd backend
python -c "
import sys; sys.path.insert(0, 'tracer')
from tracer.tracer import run_trace

code = '''
x = 10
if x > 5:
    y = 1
else:
    y = 2
'''
result = run_trace(code)
print(f'Steps: {result[\"total_steps\"]}')
for s in result['steps']:
    if s['branches_taken']:
        print(f'  Step {s[\"step_number\"]}: line {s[\"line_number\"]} → {s[\"branches_taken\"]}')
"
```

---

## API Endpoints


| Method | Endpoint                  | Description                   |
| ------ | ------------------------- | ----------------------------- |
| POST   | `/api/traces/run`         | Execute code and return trace |
| POST   | `/api/traces`             | Save a trace (auth required)  |
| GET    | `/api/traces`             | List user's traces            |
| GET    | `/api/llm/explain/stream` | Stream LLM explanation (SSE)  |
| GET    | `/api/review/due`         | Get due review cards          |
| POST   | `/api/review/{card_id}`   | Submit review rating          |
| PATCH  | `/api/profiles/me`        | Update profile settings       |


Full API documentation at `/docs` (Swagger UI).

---

## License

MIT — see [LICENSE](LICENSE)