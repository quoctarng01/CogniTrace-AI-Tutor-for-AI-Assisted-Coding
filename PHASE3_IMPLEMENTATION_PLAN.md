# Phase 3 — Spaced Repetition (SM-2) Implementation Plan

**Goal:** Make comprehension stick through systematic review scheduling.

---

## Current Status: ✅ Tests Complete

The Phase 3 infrastructure is fully implemented with comprehensive test coverage.

---

## ✅ Completed Components

### Backend

#### 3.1.1 SM-2 Algorithm (`backend/app/routers/review.py`)

- **Location:** `backend/app/routers/review.py` (lines 23-76)
- **Status:** ✅ Implemented and tested
- **Description:** SuperMemo 2 algorithm with quality ratings 0-5, easiness factor (min 1.3), interval calculation, and next review date computation.
- **Rating mapping:**
  - `again` → quality 1
  - `hard` → quality 2
  - `good` → quality 3
  - `easy` → quality 5

#### 3.1.2 Review Endpoints (`backend/app/routers/review.py`)


| Endpoint            | Method | Status        |
| ------------------- | ------ | ------------- |
| `/review/due`       | GET    | ✅ Implemented |
| `/review/{card_id}` | GET    | ✅ Implemented |
| `/review/{card_id}` | POST   | ✅ Implemented |


#### 3.1.3 Backend SM-2 Tests

- **File:** `backend/tests/unit/test_sm2.py`
- **Status:** ✅ Complete (15 tests, all passing)
- **Test coverage:**
  - Quality 3 (Good) progression: first → second → third review
  - Quality 5 (Easy): increases EF, grows interval faster
  - Quality 1-2 (Again/Hard): resets interval to 1
  - Easiness factor bounds: minimum 1.3
  - Full progression simulation
  - Reset after failure

### Frontend

#### 3.2.1 SM-2 Library (`frontend/lib/sm2.ts`)

- **Status:** ✅ Implemented and tested
- **Functions:**
  - `sm2()` — calculates next review parameters (fixed: now uses `RATING_MAP`)
  - `reviewToSM2Params()` — converts API response to SM-2 params
  - `calculateStreak()` — calculates review streak
  - `formatNextReview()` — formats review date for display

#### 3.2.2 Frontend SM-2 Tests

- **File:** `frontend/__tests__/sm2.test.ts`
- **Status:** ✅ Complete (14 tests, all passing)
- **Test coverage:**
  - Quality progression for all rating types
  - Easiness factor bounds and calculations
  - Full progression and reset scenarios
  - Rating type validation

#### 3.2.3 Review Page (`frontend/app/review/[card_id]/page.tsx`)

- **Status:** ✅ Implemented
- **Features:**
  - Auto-play animation (750ms/step)
  - Rating buttons: Again / Hard / Good / Easy
  - Post-review feedback with next review date
  - Progress bar during animation
  - Error handling and loading states

#### 3.2.4 Dashboard Integration (`frontend/app/dashboard/page.tsx`)

- **Status:** ✅ Implemented
- **Features:**
  - Review queue section with due cards
  - Streak display
  - Card metadata (interval, repetitions)
  - Link to individual review pages

#### 3.2.5 API Client (`frontend/lib/api.ts`)

- **Status:** ✅ Implemented
- **Functions:**
  - `fetchDueReviews()` — fetches due review cards
  - `fetchReviewCard()` — fetches single card with trace
  - `submitReviewRating()` — submits review rating

#### 3.2.6 E2E Test Setup

- **Files:**
  - `frontend/playwright.config.ts` — Playwright configuration
  - `frontend/e2e/review.spec.ts` — Review flow E2E tests
- **Status:** ✅ Tests written (require running app to execute)

---

## 🔲 Remaining Work

### Optional Enhancements

#### 3.3.1 First-Time User SR Tutorial

Add onboarding tooltip or modal for first-time users explaining:

> "We'll ask you about this again in 1 day, then 3 days, then 7 days — that's how you actually remember it."

---

## File Map

```
codescope/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   └── review.py          ✅ SM-2 + Endpoints
│   │   └── main.py                ✅ Routes included
│   └── tests/
│       └── unit/
│           ├── test_sm2.py        ✅ 15 tests passing
│           ├── test_tracer.py     ✅ Existing
│           └── test_validator.py  ✅ Existing
│
├── frontend/
│   ├── lib/
│   │   └── sm2.ts                 ✅ SM-2 library (fixed)
│   ├── app/
│   │   ├── dashboard/
│   │   │   └── page.tsx          ✅ Review queue display
│   │   └── review/
│   │       └── [card_id]/
│   │           └── page.tsx       ✅ Review page
│   ├── __tests__/
│   │   └── sm2.test.ts           ✅ 14 tests passing
│   ├── e2e/
│   │   ├── review.spec.ts         ✅ Tests written
│   │   └── (requires running app)
│   └── playwright.config.ts       ✅ Config created
│
└── PHASE3_IMPLEMENTATION_PLAN.md  ✅ This file
```

---

## Verification Commands

```bash
# Backend tests
cd backend && pytest tests/unit/test_sm2.py -v

# Frontend unit tests
cd frontend && npm test

# Frontend E2E tests (requires app running)
cd frontend && npx playwright test e2e/review.spec.ts

# All backend tests
cd backend && pytest -v
```

---

## Bug Fix Applied

### Fixed: SM-2 function not using `RATING_MAP`

**Problem:** The `sm2()` function in `frontend/lib/sm2.ts` had a `RATING_MAP` constant defined but was reading `params.quality` instead of using the `rating` parameter with `RATING_MAP`.

**Solution:** Updated function signature to:

```typescript
export function sm2(rating: Rating, params: Omit<SM2Params, "quality">): SM2Result {
  const { easinessFactor: ef, intervalDays: interval, repetitions: reps } = params;
  const q = RATING_MAP[rating];
  // ... rest of implementation
}
```

