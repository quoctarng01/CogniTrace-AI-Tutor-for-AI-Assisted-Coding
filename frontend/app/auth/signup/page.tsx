// frontend/app/auth/signup/page.tsx
"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signUp, getSupabase } from "@/lib/supabase";
import styles from "../auth.module.css";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    getSupabase().auth.getSession().then(({ data }) => {
      if (data?.session) router.replace("/dashboard");
    });
  }, [router]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 6) { setError("Password must be at least 6 characters."); return; }
    if (password !== confirmPassword) { setError("Passwords do not match."); return; }
    setLoading(true);
    try {
      const data = await signUp(email, password);
      if (data.user && !data.session) {
        setSuccessMessage("Account created! Check your email to confirm your account before signing in.");
      } else {
        router.push("/dashboard");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Sign up failed";
      if (msg.includes("already registered")) {
        setError("An account with this email already exists.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [email, password, confirmPassword, router]);

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </div>
        <h1 className={styles.title}>Create your account</h1>
        <p className={styles.subtitle}>
          Already have an account?{" "}
          <Link href="/auth/login" className={styles.link}>Sign in</Link>
        </p>
        {successMessage ? (
          <div className={styles.success}>
            <span>✓</span> {successMessage}
            <p className={styles.successBack}>
              <Link href="/auth/login" className={styles.link}>← Back to sign in</Link>
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="email" className={styles.label}>Email</label>
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com" required autoComplete="email" className={styles.input} />
            </div>
            <div className={styles.field}>
              <label htmlFor="password" className={styles.label}>Password</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters" required minLength={6} autoComplete="new-password" className={styles.input} />
            </div>
            <div className={styles.field}>
              <label htmlFor="confirmPassword" className={styles.label}>Confirm password</label>
              <input id="confirmPassword" type="password" value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repeat your password" required autoComplete="new-password" className={styles.input} />
            </div>
            {error && <div className={styles.error}><span>⚠</span> {error}</div>}
            <button type="submit" disabled={loading || !email || !password || !confirmPassword} className={styles.submitBtn}>
              {loading ? "Creating account..." : "Create account"}
            </button>
          </form>
        )}
        <p className={styles.footer}>
          <Link href="/" className={styles.link}>← Back to tracer</Link>
        </p>
      </div>
    </div>
  );
}
