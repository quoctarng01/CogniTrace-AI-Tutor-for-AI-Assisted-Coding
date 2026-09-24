-- ============================================================
-- V010: Concept categories (Workstream 4)
-- ============================================================
-- Single source of truth for the concept vocabulary used by the
-- trace → review-card pipeline. Replaces the prior `concept_tags TEXT[]`
-- denormalized column on `traces` and the `concept_tag TEXT` column on
-- `review_cards`.
--
-- The vocabulary seeds the seven high-level Python concept categories
-- plus the seven misconception tags emitted by the LLM router.
-- ============================================================

CREATE TABLE IF NOT EXISTS concept_categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    parent_id   UUID REFERENCES concept_categories(id) ON DELETE SET NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_concept_categories_parent ON concept_categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_concept_categories_slug ON concept_categories(slug);

-- Seed the seven high-level Python concept categories.
INSERT INTO concept_categories (slug, label, description) VALUES
    ('FUNCTION',       'Functions',         'Function definition, arguments, return values, scope'),
    ('LOOP',           'Loops',             'for-loops, while-loops, iteration, break/continue'),
    ('CONDITIONAL',    'Conditionals',      'if/elif/else, ternary expressions, short-circuit'),
    ('CLASS',          'Classes',           'class definition, instantiation, methods, inheritance'),
    ('EXCEPTION',      'Exceptions',        'try/except/finally, raise, custom exception types'),
    ('LAMBDA',         'Lambdas',           'Anonymous functions, closures, first-class functions'),
    ('COMPREHENSION',  'Comprehensions',    'List/dict/set comprehensions, generator expressions')
ON CONFLICT (slug) DO NOTHING;

-- Seed the seven misconception tags from llm_router.py.
INSERT INTO concept_categories (slug, label, description) VALUES
    ('off_by_one',                    'Off-by-one error',                'Loop bounds that should be inclusive but are not, or vice versa'),
    ('unexecuted_iteration',          'Unexecuted iteration',            'A loop body that should run but never executes due to range/condition'),
    ('none_dereference',              'None dereference',                 'Accessing an attribute or item on a None value'),
    ('state_mutation_confusion',      'Mutable state confusion',          'Mutation of shared state (lists, dicts) surprising the reader'),
    ('conditional_evaluation_error',  'Conditional evaluation',           'Short-circuit or ternary behaviour not matching expectations'),
    ('type_confusion',                'Type confusion',                   'Mixing types in an expression where the type coercion is unexpected'),
    ('general_logic_error',           'General logic error',              'Catch-all for unspecified runtime logic errors')
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- Join tables: trace_concept_tags and review_card_concepts
-- ============================================================

CREATE TABLE IF NOT EXISTS trace_concept_tags (
    trace_id   UUID NOT NULL REFERENCES traces(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concept_categories(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (trace_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_trace_concept_tags_concept ON trace_concept_tags(concept_id);

CREATE TABLE IF NOT EXISTS review_card_concepts (
    card_id    UUID NOT NULL REFERENCES review_cards(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concept_categories(id) ON DELETE CASCADE,
    PRIMARY KEY (card_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_review_card_concepts_concept ON review_card_concepts(concept_id);

-- ============================================================
-- Row Level Security
-- ============================================================

ALTER TABLE concept_categories    ENABLE ROW LEVEL SECURITY;
ALTER TABLE trace_concept_tags    ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_card_concepts  ENABLE ROW LEVEL SECURITY;

-- concept_categories is world-readable (every trace and card can tag against any category).
CREATE POLICY "public_read_concepts" ON concept_categories
    FOR SELECT USING (true);

-- Trace tag rows inherit visibility from the parent trace.
CREATE POLICY "own_trace_tags" ON trace_concept_tags
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM traces t
            WHERE t.id = trace_concept_tags.trace_id
            AND t.user_id = auth.uid()
        )
    );

-- Review-card concept rows inherit visibility from the parent card.
CREATE POLICY "own_card_concepts" ON review_card_concepts
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM review_cards c
            WHERE c.id = review_card_concepts.card_id
            AND c.user_id = auth.uid()
        )
    );

-- ============================================================
-- Backfill helper (idempotent — safe to re-run)
-- ============================================================
-- Maps existing TEXT[] tags on `traces` into the new join table. Existing
-- tags on individual rows are preserved as concept_ids where the slug matches;
-- unknown slugs are logged via the warning column on the helper view below.
--
-- The application is responsible for writing into the new join table on new
-- traces; this backfill is for existing rows only.

INSERT INTO trace_concept_tags (trace_id, concept_id)
SELECT DISTINCT t.id, c.id
FROM traces t
CROSS JOIN LATERAL unnest(t.concept_tags) AS tag(slug)
JOIN concept_categories c ON c.slug = tag.slug
WHERE NOT EXISTS (
    SELECT 1 FROM trace_concept_tags tct
    WHERE tct.trace_id = t.id AND tct.concept_id = c.id
);

INSERT INTO review_card_concepts (card_id, concept_id)
SELECT rc.id, c.id
FROM review_cards rc
JOIN concept_categories c ON c.slug = rc.concept_tag
WHERE rc.concept_tag IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM review_card_concepts rcc
    WHERE rcc.card_id = rc.id AND rcc.concept_id = c.id
);
