// File: frontend/app/examples/page.tsx
'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { fetchExamples } from '@/lib/api';
import type { Example } from '@/lib/api';
import styles from './page.module.css';

// Color assigned to each category badge
const CATEGORY_COLORS: Record<string, string> = {
  comprehensions: '#a855f7',
  none_handling: '#6b7280',
  async_await: '#06b6d4',
  decorators: '#f59e0b',
  oop: '#22c55e',
  type_hints: '#3b82f6',
  context_managers: '#f97316',
  closures: '#ec4899',
};

function getCategoryColor(cat: string): string {
  return CATEGORY_COLORS[cat] ?? '#71717a';
}

function ExampleCard({ example }: { example: Example }) {
  const color = getCategoryColor(example.category);
  const firstLine = example.code.split('\n')[0];

  return (
    <Link href={`/examples/${example.id}`} className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.badge} style={{ backgroundColor: color + '20', color }}>
          {example.category.replace('_', ' ')}
        </span>
      </div>
      <h3 className={styles.cardTitle}>{example.title}</h3>
      <p className={styles.cardWhy}>{example.why_ai_generates_this}</p>
      <pre className={styles.codePreview}>
        <code>{firstLine}</code>
      </pre>
      <div className={styles.cardFooter}>
        <span className={styles.meta}>
          {example.annotations.length} annotation{example.annotations.length !== 1 ? 's' : ''}
        </span>
        <span className={styles.viewLink}>View →</span>
      </div>
    </Link>
  );
}

export default function ExamplesPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchExamples>> | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const LIMIT = 20;

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchExamples(activeCategory ?? undefined, LIMIT, page * LIMIT)
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, [activeCategory, page]);

  const examples = data?.examples ?? [];
  const total = data?.total ?? 0;
  const categories = [...new Set(examples.map(e => e.category))].sort();

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className={styles.page}>
      {/* Top bar */}
      <header className={styles.topBar}>
        <Link href="/" className={styles.brandLink}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </Link>
        <nav className={styles.navLinks}>
          <Link href="/tracer" className={styles.navLink}>
            New Trace
          </Link>
          <Link href="/examples" className={`${styles.navLink} ${styles.navLinkActive}`}>
            Examples
          </Link>
        </nav>
      </header>

      <main className={styles.main}>
        <p className={styles.intro}>
          Curated AI-generated Python patterns. Each example explains <em>why</em> AI writes this
          code. Save any example to your review queue.
        </p>

        {/* Category filter tabs */}
        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${activeCategory === null ? styles.tabActive : ''}`}
            onClick={() => {
              setActiveCategory(null);
              setPage(0);
            }}
          >
            All
          </button>
          {categories.map(cat => (
            <button
              key={cat}
              className={`${styles.tab} ${activeCategory === cat ? styles.tabActive : ''}`}
              onClick={() => {
                setActiveCategory(cat === activeCategory ? null : cat);
                setPage(0);
              }}
              style={
                activeCategory === cat
                  ? { borderColor: getCategoryColor(cat), color: getCategoryColor(cat) }
                  : {}
              }
            >
              {cat.replace('_', ' ')}
            </button>
          ))}
        </div>

        {/* Loading state */}
        {loading && (
          <div className={styles.loading}>
            <span>◈</span> Loading examples...
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className={styles.error}>
            <span>⚠</span> {error}
            <button onClick={() => setPage(page)} className={styles.retryBtn}>
              Retry
            </button>
          </div>
        )}

        {/* Results */}
        {!loading && !error && (
          <>
            <p className={styles.resultCount}>
              {total} example{total !== 1 ? 's' : ''}
              {activeCategory ? ` in ${activeCategory.replace('_', ' ')}` : ''}
            </p>

            {examples.length === 0 ? (
              <p className={styles.empty}>No examples found.</p>
            ) : (
              <>
                <div className={styles.grid}>
                  {examples.map(ex => (
                    <ExampleCard key={ex.id} example={ex} />
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className={styles.pagination}>
                    <button
                      disabled={page === 0}
                      onClick={() => setPage(page - 1)}
                      className={styles.pageBtn}
                    >
                      ← Prev
                    </button>
                    <span className={styles.pageInfo}>
                      Page {page + 1} of {totalPages}
                    </span>
                    <button
                      disabled={page >= totalPages - 1}
                      onClick={() => setPage(page + 1)}
                      className={styles.pageBtn}
                    >
                      Next →
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
