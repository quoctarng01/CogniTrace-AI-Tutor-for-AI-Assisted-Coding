import Link from 'next/link';
import styles from './page.module.css';

const CODE_SAMPLES = [
  {
    title: 'List Comprehension',
    code: `numbers = [1, 2, 3, 4, 5]
squares = [x**2 for x in numbers]
# [1, 4, 9, 16, 25]`,
    explanation: 'Creates a new list by applying an expression to each item',
  },
  {
    title: 'Conditional Logic',
    code: `age = 25
status = "adult" if age >= 18 else "minor"`,
    explanation: 'Ternary operator for concise conditional assignment',
  },
  {
    title: 'Function with Loop',
    code: `def fibonacci(n):
    a, b = 0, 1
    for i in range(n):
        a, b = b, a + b
    return a`,
    explanation: 'Generates fibonacci sequence iteratively',
  },
];

const FEATURES = [
  {
    icon: '🎯',
    title: 'Step-by-Step Execution',
    description:
      'Watch your Python code execute one line at a time with real-time variable state updates.',
  },
  {
    icon: '🔀',
    title: 'Branch Detection',
    description:
      'See exactly which if/else branches fire and why. Understand loop iterations visually.',
  },
  {
    icon: '🤖',
    title: 'AI Explanations',
    description:
      "Get contextual explanations for any line powered by LLMs. Understand the 'why', not just the 'what'.",
  },
  {
    icon: '📚',
    title: 'Spaced Repetition',
    description:
      'Review tricky code patterns using proven spaced repetition algorithms. Retain knowledge longer.',
  },
];

export default function Home() {
  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </div>
        <nav className={styles.nav}>
          <Link href="/tracer" className={styles.navLink}>
            Try Now
          </Link>
          <Link href="/dashboard" className={styles.navLink}>
            Dashboard
          </Link>
        </nav>
      </header>

      {/* Hero */}
      <section className={styles.hero}>
        <div className={styles.heroContent}>
          <h1 className={styles.heroTitle}>
            Pasted AI-generated code.
            <br />
            <span className={styles.heroHighlight}>No idea why it is breaking.</span>
          </h1>
          <p className={styles.heroSubtitle}>
            CodeScope traces how Cursor, Copilot, and ChatGPT write Python —
            variable by variable, branch by branch — then schedules spaced reviews
            so you actually remember what you shipped.
          </p>
          <div className={styles.heroCta}>
            <Link href="/tracer" className={styles.primaryBtn}>
              Start Tracing →
            </Link>
            <a href="#features" className={styles.secondaryBtn}>
              Learn More
            </a>
          </div>
        </div>
        <div className={styles.heroVisual}>
          <div className={styles.codeWindow}>
            <div className={styles.windowBar}>
              <span className={styles.dot} />
              <span className={styles.dot} />
              <span className={styles.dot} />
              <span className={styles.windowTitle}>fibonacci.py</span>
            </div>
            <pre className={styles.codeBlock}>
              <code>{`def fibonacci(n):
    a, b = 0, 1
    for i in range(n):
        a, b = b, a + b
    return a

result = fibonacci(8)`}</code>
            </pre>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className={styles.features}>
        <h2 className={styles.sectionTitle}>How It Works</h2>
        <div className={styles.featureGrid}>
          {FEATURES.map(feature => (
            <div key={feature.title} className={styles.featureCard}>
              <span className={styles.featureIcon}>{feature.icon}</span>
              <h3 className={styles.featureTitle}>{feature.title}</h3>
              <p className={styles.featureDescription}>{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Code Examples */}
      <section className={styles.examples}>
        <h2 className={styles.sectionTitle}>Try Common Patterns</h2>
        <div className={styles.exampleGrid}>
          {CODE_SAMPLES.map(example => (
            <div key={example.title} className={styles.exampleCard}>
              <h3 className={styles.exampleTitle}>{example.title}</h3>
              <pre className={styles.exampleCode}>
                <code>{example.code}</code>
              </pre>
              <p className={styles.exampleExplanation}>{example.explanation}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className={styles.cta}>
        <h2 className={styles.ctaTitle}>Ready to Understand Your Code?</h2>
        <p className={styles.ctaSubtitle}>
          Start tracing Python code in your browser. No setup required.
        </p>
        <Link href="/tracer" className={styles.primaryBtn}>
          Launch CodeScope →
        </Link>
      </section>

      {/* Footer */}
      <footer className={styles.footer}>
        <p>
          Built for CS students and developers learning Python. Powered by bytecode tracing and AI.
        </p>
        <p className={styles.footerMeta}>
          <Link href="/dashboard">Dashboard</Link> · <Link href="/tracer">Tracer</Link>
        </p>
      </footer>
    </div>
  );
}
