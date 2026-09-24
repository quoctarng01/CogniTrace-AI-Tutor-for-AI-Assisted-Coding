# What was fixed

## 1. RLS policy silently hid every review_events row from the user
File: `backend/migrations/V016__review_events_rls_fix.sql`

The V015 policy was `USING (user_id = auth.uid())` where `auth.uid()` returns `auth.users.id`, but `review_events.user_id` stores `profiles.id`. The two are different UUIDs in CogniTrace, so RLS hid all rows.

Replaced with a subquery that maps the calling user to their profile id:
```sql
USING (user_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()))
```

## 2. /api/review/trajectory was a 404 by route collision
File: `backend/app/routers/review.py`

`@router.get("/{card_id}")` was registered **before** `@router.get("/trajectory")`, so FastAPI matched `/trajectory` as `card_id = "trajectory"` and returned "Card not found".

Moved the `/trajectory` route (and its Pydantic models `TrajectoryPoint`, `TrajectoryConcept`, `TrajectoryResponse`) **above** the `/{card_id}` catch-all.

## Verification

End-to-end call as `quoctrang613@gmail.com` against the running backend:
```
GET http://127.0.0.1:8001/api/review/trajectory?days=30
Authorization: Bearer <user JWT>
-> 200 OK
{
  "concepts": [6 concept lines, each with mastery points over time],
  "date_range": { "start": "2026-08-25", "end": "2026-09-06" },
  "total_events": 47,
  "days": 30
}
```

Backend now running with `--reload` on 127.0.0.1:8001 and ::1:8001.

## What to do

Reload http://127.0.0.1:3000/dashboard/mastery in the browser. The chart should now render 6 concept lines from 2026-08-25 to 2026-09-06.
