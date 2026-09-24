"""
Seed review_events for /dashboard/mastery testing.

Inserts ~50 fake review events across 6 concepts over the last 14 days,
shaped exactly like the events that /api/review/{card_id} would write
during real use. Designed to give the mastery-trajectory chart real
data points so you can iterate on the visualization quickly.

Usage (PowerShell):
    $env:DATABASE_URL = "postgresql://postgres.[ref]:[pw]@...supabase.com:5432/postgres"
    cd backend
    python scripts/seed_review_events.py

Options:
    --user-id <uuid>   Seed a specific profile instead of auto-detecting
                       the first profile from auth.users (handy when
                       you've created several accounts).
    --days 14          Time window in days (default 14)
    --keep             Don't delete existing events first

Notes:
  * This script connects with the SERVICE ROLE database role so it can
    bypass RLS. NEVER expose this connection string to the browser.
  * All SQL is parameterized — no f-string substitution into queries.
  * The script is idempotent. Re-running clears the seeded events and
    re-inserts them with fresh timestamps so the chart shows data
    relative to "now".
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

try:
    import psycopg2  # noqa: F401  (used in main())
    from psycopg2.extras import execute_values
except ImportError:
    psycopg2 = None  # type: ignore[assignment]
    execute_values = None  # type: ignore[assignment]


# ── SM-2 helpers ──────────────────────────────────────────────────────────
# Mirrors app/routers/review.py:sm2_calculate. Kept duplicated rather than
# imported so the script stays runnable without the backend's full deps.

MIN_EF = 1.3
RATING_QUALITY = {"again": 1, "hard": 2, "good": 3, "easy": 5}


def sm2_step(quality: int, ef: float, interval: int, reps: int) -> tuple[float, int, int]:
    new_ef = max(MIN_EF, ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    if quality < 2:
        return new_ef, 1, 0
    if quality == 2:
        return new_ef, max(1, round(interval * 0.5)), max(1, reps // 2)
    if reps == 0:
        return new_ef, 1, 1
    if reps == 1:
        return new_ef, 6, reps + 1
    return new_ef, round(interval * new_ef), reps + 1


# ── Seed scenario ─────────────────────────────────────────────────────────
# Six concepts, each with a distinct shape:
#   - "off_by_one"        : steady climber (good ratings mostly)
#   - "state_mutation..." : oscillating (alternating good/hard)
#   - "none_dereference"  : late starter (nothing for first week, then climbing)
#   - "off_by_two"        : dip-then-recover (a few "again"s then back up)
#   - "type_confusion"    : late mastery (long flat then climbs)
#   - "general_logic"     : recent_miss demo (climbed, recent hard in last 3 days)

CONCEPT_PROFILES: list[tuple[str, list[str]]] = [
    ("off_by_one",             ["good", "good", "good", "good", "good", "good", "good", "easy"]),
    ("state_mutation_confusion", ["good", "hard", "good", "hard", "good", "hard", "good", "good"]),
    ("none_dereference",       ["good", "good", "good", "good", "good", "good", "good", "easy"]),
    ("off_by_two",             ["again", "hard", "good", "good", "good", "good", "good", "good"]),
    ("type_confusion",         ["hard", "good", "good", "good", "good", "good", "easy", "easy"]),
    ("general_logic_error",    ["good", "good", "good", "good", "good", "good", "hard", "hard"]),
]


def build_events_for_concept(
    user_id: str,
    card_id: str,
    trace_id: str | None,
    concept_tag: str,
    ratings: list[str],
    started_at: datetime,
) -> tuple[list[tuple], tuple[float, int, int]]:
    """Walk the SM-2 chain for one concept and emit one event per rating.

    Returns ``(events, final_state)`` where ``final_state`` is the
    ``(easiness_factor, interval_days, repetitions)`` triple AFTER the
    last rating — used to populate the ``review_cards`` row so it makes
    sense if anyone queries it independently of the event log.
    """
    events: list[tuple] = []
    ef, interval, reps = 2.5, 1, 0
    occurred_at = started_at

    for i, rating in enumerate(ratings):
        quality = RATING_QUALITY[rating]
        prev_ef, prev_interval, prev_reps = ef, interval, reps
        ef, interval, reps = sm2_step(quality, ef, interval, reps)
        mastery = reps / (reps + 3)

        events.append(
            (
                str(uuid.uuid4()),
                user_id,
                card_id,
                trace_id,
                concept_tag,
                rating,
                quality,
                prev_reps,
                prev_interval,
                round(prev_ef, 2),
                reps,
                interval,
                round(ef, 2),
                round(mastery, 4),
                occurred_at,
            )
        )
        # Spread events across the requested window. Jitter by ±20%
        # so the chart doesn't look like a perfect metronome.
        jitter = 0.8 + 0.4 * ((i * 37 % 100) / 100.0)
        occurred_at = occurred_at + timedelta(days=1.5 * jitter)

    return events, (round(ef, 2), interval, reps)


# ── SQL ────────────────────────────────────────────────────────────────────

SEED_EVENT_INSERT = """
INSERT INTO review_events (
    id, user_id, card_id, trace_id, concept_tag,
    rating, quality,
    prev_repetitions, prev_interval_days, prev_easiness_factor,
    new_repetitions, new_interval_days, new_easiness_factor,
    mastery_after, occurred_at
) VALUES %s
"""

SEED_DELETE = "DELETE FROM review_events WHERE user_id = %s"

# Also remove cards the script previously created (so re-runs don't leak).
# Match on the deterministic concept_tag + user_id combo, NOT on trace_id
# (cards may or may not have a trace attached).
SEED_CARDS_DELETE = """
DELETE FROM review_cards
WHERE user_id = %s
  AND concept_tag IN (
    'off_by_one', 'state_mutation_confusion', 'none_dereference',
    'off_by_two', 'type_confusion', 'general_logic_error'
  )
  AND trace_id IS NULL
"""

# Insert one card per concept before the events go in. trace_id is
# nullable, so we leave it NULL — matches the backfill case from the
# V015 migration comment. easiness_factor/interval_days/repetitions are
# seeded to the post-mastery-final-event values so the row makes sense
# if anyone queries it independently of the event log.
SEED_CARD_INSERT = """
INSERT INTO review_cards (
    id, user_id, trace_id, concept_tag,
    easiness_factor, interval_days, repetitions,
    next_review_date, last_reviewed_at, created_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""

USER_RESOLVE_SQL = """
SELECT p.id, u.email
FROM profiles p
JOIN auth.users u ON u.id = p.user_id
ORDER BY p.created_at ASC
LIMIT 1
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed review_events for mastery-trajectory testing.")
    p.add_argument("--user-id", help="Specific profile UUID to seed. Default: first profile in auth.users.")
    p.add_argument("--days", type=int, default=14, help="Time window in days (default 14).")
    p.add_argument("--keep", action="store_true", help="Don't delete existing events first.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan but do not touch the database.",
    )
    return p.parse_args()


def resolve_user_id(cur, requested: str | None) -> str:
    if requested:
        cur.execute("SELECT id FROM profiles WHERE id = %s", (requested,))
        row = cur.fetchone()
        if not row:
            print(
                f"ERROR: --user-id {requested} not found in profiles. "
                "Sign up in the app first, or omit --user-id to use the first profile.",
                file=sys.stderr,
            )
            sys.exit(2)
        return row[0]

    cur.execute(USER_RESOLVE_SQL)
    row = cur.fetchone()
    if not row:
        print(
            "ERROR: no profiles found. Sign up at least one user in the app "
            "before seeding.",
            file=sys.stderr,
        )
        sys.exit(2)
    print(f"  resolved user_id={row[0]} (email={row[1]})")
    return row[0]


def main() -> int:
    args = parse_args()

    if args.dry_run:
        # Don't require psycopg2 for a no-DB preview.
        print(
            f"[dry-run] would seed {len(CONCEPT_PROFILES)} concepts × "
            f"{sum(len(r) for _, r in CONCEPT_PROFILES)} events over "
            f"{args.days} days"
        )
        for tag, ratings in CONCEPT_PROFILES:
            print(f"  - {tag}: {ratings}")
        return 0

    if psycopg2 is None:
        print(
            "ERROR: psycopg2 not installed. Run:\n"
            "  pip install psycopg2-binary\n"
            "Then retry.",
            file=sys.stderr,
        )
        return 2

    # Prefer explicit DATABASE_URL. Fall back to building one from
    # SUPABASE_URL + SUPABASE_SERVICE_KEY in the environment.
    #
    # NOTE: Supabase now blocks the pooler's "tenant/user" lookup unless
    # you also pass `options=reference=...`. Simpler and more reliable:
    # connect directly to the DB host (`db.<ref>.supabase.co:5432`).
    # The service-role key is also accepted as the postgres password
    # on the direct host (Supabase mirrors them at project creation).
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        supabase_url = os.environ.get("SUPABASE_URL", "")
        password = (
            os.environ.get("SUPABASE_DB_PASSWORD")
            or os.environ.get("SUPABASE_SERVICE_KEY")
            or ""
        )
        if supabase_url and password:
            # Extract project ref: https://cyzpvltrayvpdooxgmaj.supabase.co
            #                         -> cyzpvltrayvpdooxgmaj
            ref = (
                supabase_url.removeprefix("https://")
                .removeprefix("http://")
                .split(".")[0]
            )
            dsn = (
                f"postgresql://postgres:{password}"
                f"@db.{ref}.supabase.co:5432/postgres"
            )
        else:
            print(
                "ERROR: DATABASE_URL not set, and SUPABASE_URL/\n"
                "       SUPABASE_SERVICE_KEY are not in the environment.\n"
                "       Set one of:\n"
                "         $env:DATABASE_URL = 'postgresql://postgres:PASSWORD@db.YOUR_REF.supabase.co:5432/postgres'\n"
                "         source backend/.env  (sets SUPABASE_URL + SUPABASE_SERVICE_KEY)",
                file=sys.stderr,
            )
            return 2

    print(f"Connecting to {dsn.split('@')[-1]} ...")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            user_id = resolve_user_id(cur, args.user_id)

            if not args.keep:
                # Order matters: events depend on cards, so clear cards second.
                cur.execute(SEED_DELETE, (user_id,))
                print(f"  cleared {cur.rowcount} existing events for user {user_id}")
                cur.execute(SEED_CARDS_DELETE, (user_id,))
                print(f"  cleared {cur.rowcount} stale seed-cards for user {user_id}")

            now = datetime.now(UTC)
            # First event lands `days` ago; subsequent events walk forward
            # from there. This means the most recent event is `now`, which
            # is exactly when "today" events should show on the chart.
            all_events: list[tuple] = []
            started_at = now - timedelta(days=args.days)
            for concept_tag, ratings in CONCEPT_PROFILES:
                # One fake card + (optional) trace per concept. trace_id
                # is nullable per the V015 schema, so we leave it NULL —
                # matches the backfill case from the migration comment.
                card_id = str(uuid.uuid4())
                events, (final_ef, final_interval, final_reps) = build_events_for_concept(
                    user_id=user_id,
                    card_id=card_id,
                    trace_id=None,
                    concept_tag=concept_tag,
                    ratings=ratings,
                    started_at=started_at,
                )
                all_events.extend(events)

                # Insert the card row so the FK from review_events
                # resolves. created_at = started_at so card "age" lines
                # up with the first event.
                cur.execute(
                    SEED_CARD_INSERT,
                    (
                        card_id,
                        user_id,
                        None,                # trace_id (nullable)
                        concept_tag,
                        final_ef,
                        final_interval,
                        final_reps,
                        (now + timedelta(days=final_interval)).date(),
                        now,                 # last_reviewed_at = most recent event
                        started_at,          # created_at
                    ),
                )

                # Stagger concept starts so they don't all begin on the
                # same day; makes the chart look like real usage.
                started_at = started_at + timedelta(days=0.5)

            execute_values(cur, SEED_EVENT_INSERT, all_events)
            print(f"  inserted {len(CONCEPT_PROFILES)} cards + {len(all_events)} events")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("Done. Refresh http://127.0.0.1:3000/dashboard/mastery to see the chart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
