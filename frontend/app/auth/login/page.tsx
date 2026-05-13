// frontend/app/auth/login/page.tsx
"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signIn, getSupabase } from "@/lib/supabase";
import styles from "../auth.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSupabase().auth.getSession().then(({ data }) => {
      if (data?.session) router.replace("/dashboard");
    });
  }, [router]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signIn(email, password);
      // Verify localStorage is accessible before navigating
      await new Promise(resolve => setTimeout(resolve, 200));
      const stored = localStorage.getItem("codescope-manual-session");
      console.log("[DEBUG] Login - verifying localStorage before nav:", stored ? "EXISTS" : "NULL");
      if (!stored) {
        // Try one more time after a delay
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      router.replace("/dashboard");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Login failed";
      if (msg.includes("Invalid login credentials")) {
        setError("Invalid email or password. Please try again.");
      } else if (msg.includes("Email not confirmed")) {
        setError("Email not confirmed. Check your inbox for a confirmation email.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [email, password, router]);

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </div>
        <h1 className={styles.title}>Sign in to your account</h1>
        <p className={styles.subtitle}>
          New here?{" "}
          <Link href="/auth/signup" className={styles.link}>Create an account</Link>
        </p>
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="email" className={styles.label}>Email</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com" required autoComplete="email" className={styles.input} />
          </div>
          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>Password</label>
            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password" required autoComplete="current-password" className={styles.input} />
          </div>
          {error && <div className={styles.error}><span>⚠</span> {error}</div>}
          <button type="submit" disabled={loading || !email || !password} className={styles.submitBtn}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <p className={styles.footer}>
          <Link href="/" className={styles.link}>← Back to tracer</Link>
        </p>
      </div>
    </div>
  );
}
