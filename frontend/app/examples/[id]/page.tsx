// File: frontend/app/examples/[id]/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { fetchExample, saveExampleToReview, type Example } from "@/lib/api";
import styles from "./page.module.css";

// Load syntax highlighter only on the client (SSR is not needed)
const CodeBlock = dynamic(
  () =>
    import("react-syntax-highlighter/dist/esm/prism-light").then((mod) => {
      const { PrismLight } = mod;
      // Import languages you need
      try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const python = require("react-syntax-highlighter/dist/esm/languages/prism/python").default;
        PrismLight.registerLanguage("python", python);
      } catch {
        // Language may already be registered
      }
      return function CodeBlock({ code }: { code: string }) {
        const SyntaxHighlighter = mod.default;
        return (
          <SyntaxHighlighter language="python" style={undefined} customStyle={{ margin: 0 }}>
            {code}
          </SyntaxHighlighter>
        );
      };
    }),
  { ssr: false, loading: () => <pre className={styles.codeFallback}><code>Loading...</code></pre> },
);

type SaveState = "idle" | "saving" | "saved" | "auth_required" | "error";

// Color per annotation type
const TYPE_COLORS: Record<string, string> = {
  iterator: "#3b82f6", scope: "#a855f7", filter: "#22c55e", guard: "#f97316",
  assignment: "#ec4899", function_call: "#f59e0b", passthrough: "#3b82f6",
  side_effect: "#f59e0b", async_cm: "#06b6d4", executor: "#f97316",
  offload: "#f97316", yield: "#a855f7", body: "#22c55e", cleanup: "#f59e0b",
  metadata_preservation: "#a855f7", enforcement: "#22c55e", validation: "#f59e0b",
  rollback: "#f97316", commit: "#22c55e", begin: "#06b6d4",
  nonlocal: "#f59e0b", mutation: "#ec4899", partial: "#a855f7",
  factory: "#22c55e", typevar: "#f59e0b", parameterized: "#06b6d4",
  generic_class: "#a855f7", callable_sig: "#3b82f6", nested_call: "#a855f7",
  coalesce: "#06b6d4", ternary: "#a855f7", sentinel: "#f59e0b",
  default: "#6b7280", config_layer: "#3b82f6", func_layer: "#a855f7",
  execution_layer: "#22c55e", init: "#6b7280", callable_layer: "#a855f7",
  abc: "#3b82f6", contract: "#f59e0b", boilerplate: "#6b7280",
  mutable_default: "#f97316", mixin: "#a855f7", mixin_usage: "#22c55e",
  self_reflection: "#06b6d4", enter: "#06b6d4", exit: "#f59e0b",
  timing: "#f59e0b", async_wait: "#06b6d4", closure_var: "#a855f7",
  dedup: "#06b6d4", range_check: "#22c55e",
};

function getTypeColor(type: string): string {
  return TYPE_COLORS[type] ?? "#71717a";
}

export default function ExampleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const exampleId = params.id as string;

  const [example, setExample] = useState<Example | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchExample(exampleId)
      .then(setExample)
      .catch((err) => {
        if (err instanceof Error && err.message === "EXAMPLE_NOT_FOUND") {
          setError("Example not found.");
        } else {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      })
      .finally(() => setLoading(false));
  }, [exampleId]);

  const handleSave = async () => {
    setSaveState("saving");
    try {
      const result = await saveExampleToReview(exampleId);
      setSaveState("saved");
      setSaveMessage(result.message);
    } catch (err) {
      if (err instanceof Error && err.message === "AUTH_REQUIRED") {
        router.push("/auth/login");
        return;
      }
      if (err instanceof Error && err.message === "UPGRADE_REQUIRED") {
        setSaveState("error");
        setSaveMessage("This is a Pro feature. Upgrade to save examples.");
        return;
      }
      setSaveState("error");
      setSaveMessage(err instanceof Error ? err.message : "Failed to save");
    }
  };

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loading}><span>◈</span> Loading...</div>
      </div>
    );
  }

  if (error || !example) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <Link href="/examples" className={styles.backLink}>← Examples</Link>
        </header>
        <div className={styles.errorBanner}><span>⚠</span> {error ?? "Not found"}</div>
      </div>
    );
  }

  const codeLines = example.code.split("\n");
  const intervals = Array.isArray(example.review_interval)
    ? example.review_interval
    : String(example.review_interval).split(",").map((s) => s.trim()).filter(Boolean);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link href="/examples" className={styles.backLink}>← Examples</Link>
        <span className={styles.badge}>{example.category.replace("_", " ")}</span>
        <div />
      </header>

      <main className={styles.main}>
        {/* Title + why AI generates this */}
        <section className={styles.titleSection}>
          <h1 className={styles.title}>{example.title}</h1>
          <div className={styles.whyBox}>
            <span className={styles.whyLabel}>Why AI generates this</span>
            {example.why_ai_generates_this}
          </div>
        </section>

        {/* Code + annotations */}
        <section className={styles.codeSection}>
          <h2 className={styles.sectionLabel}>Code</h2>
          <div className={styles.codeBox}>
            <CodeBlock code={example.code} />
          </div>

          {example.annotations.length > 0 && (
            <div className={styles.annotations}>
              {example.annotations.map((ann, i) => (
                <div key={i} className={styles.annotation}>
                  <span className={styles.annLine}>L{ann.line}</span>
                  <span
                    className={styles.annType}
                    style={{ color: getTypeColor(ann.type), backgroundColor: getTypeColor(ann.type) + "15" }}
                  >
                    {ann.type}
                  </span>
                  <span className={styles.annText}>{ann.text}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Explanation */}
        <section className={styles.explanationSection}>
          <h2 className={styles.sectionLabel}>Explanation</h2>
          <p className={styles.explanation}>{example.explanation}</p>
        </section>

        {/* Common mistakes */}
        {example.common_mistakes.length > 0 && (
          <section className={styles.mistakesSection}>
            <h2 className={styles.sectionLabel}>Common Mistakes</h2>
            <ul className={styles.mistakesList}>
              {example.common_mistakes.map((m, i) => (
                <li key={i} className={styles.mistake}>{m}</li>
              ))}
            </ul>
          </section>
        )}

        {/* Save to queue */}
        <section className={styles.saveSection}>
          {saveState === "saved" ? (
            <div className={styles.savedBanner}>
              <span>✓</span> {saveMessage}
              <Link href="/dashboard" className={styles.dashboardLink}>Go to Dashboard →</Link>
            </div>
          ) : saveState === "error" ? (
            <div className={styles.errorBanner}>
              <span>⚠</span> {saveMessage}
              <button onClick={handleSave} className={styles.retryBtn}>Try Again</button>
            </div>
          ) : (
            <button
              onClick={handleSave}
              disabled={saveState === "saving"}
              className={styles.saveBtn}
            >
              {saveState === "saving" ? "Saving..." : "Save to My Review Queue"}
            </button>
          )}
          <p className={styles.reviewHint}>
            Review interval: {intervals.join(" → ")} days
          </p>
        </section>
      </main>
    </div>
  );
}
