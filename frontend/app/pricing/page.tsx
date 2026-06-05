'use client';

import Link from 'next/link';
import styles from './page.module.css';

export default function Pricing() {
  return (
    <main className={styles.container}>
      <h1>Simple, transparent pricing</h1>
      <div className={styles.tiers}>
        <div className={styles.freeTier}>
          <h2>Free</h2>
          <p className={styles.price}>$0<span>/month</span></p>
          <ul>
            <li>50 traces per month</li>
            <li>AI explanations</li>
            <li>Spaced repetition review</li>
          </ul>
          <Link href="/auth/signup" className={styles.cta}>Get Started</Link>
        </div>
        <div className={styles.proTier}>
          <h2>Pro</h2>
          <p className={styles.price}>$15<span>/month</span></p>
          <ul>
            <li>Unlimited traces</li>
            <li>AI explanations</li>
            <li>Spaced repetition review</li>
            <li>Shared trace links</li>
            <li>Priority support</li>
          </ul>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const email = (e.currentTarget.elements.namedItem('email') as HTMLInputElement)?.value;
              await fetch('/api/upgrade-request', {
                method: 'POST',
                body: JSON.stringify({ email, tier: 'pro' }),
              });
              alert("We'll send you a payment link within 24 hours.");
            }}
          >
            <input name="email" type="email" placeholder="your@email.com" required />
            <button type="submit">Get Pro Access</button>
          </form>
        </div>
      </div>
    </main>
  );
}
