"use client";

import { type ReactNode, type ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  children: ReactNode;
}

const variantStyles: Record<string, string> = {
  primary:
    "background: linear-gradient(135deg, #1f6feb, #388bfd); color: white; border: none;",
  secondary:
    "background: #161b22; color: #e6edf3; border: 1px solid #30363d;",
  danger:
    "background: rgba(248,81,73,0.1); color: #f85149; border: 1px solid rgba(248,81,73,0.3);",
  ghost:
    "background: transparent; color: #8b949e; border: none;",
};

const sizeStyles: Record<string, string> = {
  sm: "padding: 4px 12px; font-size: 12px; border-radius: 4px;",
  md: "padding: 8px 16px; font-size: 13px; border-radius: 6px;",
  lg: "padding: 12px 24px; font-size: 15px; border-radius: 8px;",
};

export function Button({
  variant = "primary",
  size = "md",
  children,
  style,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "6px",
        fontWeight: 600,
        cursor: "pointer",
        transition: "all 0.15s ease",
        fontFamily: "inherit",
        ...(style as React.CSSProperties ?? {}),
        ...Object.fromEntries(
          [
            ...variantStyles[variant].split(";").filter(Boolean).map((s) => {
              const [k, v] = s.split(":").map((x) => x.trim());
              return [k.replace(/-([a-z])/g, (_, c) => c.toUpperCase()), v];
            }),
            ...sizeStyles[size].split(";").filter(Boolean).map((s) => {
              const [k, v] = s.split(":").map((x) => x.trim());
              return [k.replace(/-([a-z])/g, (_, c) => c.toUpperCase()), v];
            }),
          ].filter(([k]) => k)
        ) as React.CSSProperties,
      }}
    >
      {children}
    </button>
  );
}
