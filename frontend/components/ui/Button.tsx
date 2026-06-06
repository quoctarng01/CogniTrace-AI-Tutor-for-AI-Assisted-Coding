'use client';

import { type ReactNode, type ButtonHTMLAttributes, useState } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  children: ReactNode;
}

const variantStyles: Record<string, string> = {
  primary: 'background: var(--accent); color: var(--btn-text); border: 1px solid transparent;',
  secondary: 'background: var(--surface); color: var(--text); border: 1px solid var(--border);',
  danger: 'background: var(--danger-bg); color: var(--danger); border: 1px solid var(--danger-border);',
  ghost: 'background: transparent; color: var(--text-muted); border: 1px solid transparent;',
};

const hoverStyles: Record<string, string> = {
  primary: 'background: var(--accent-hover); color: var(--btn-text); border: 1px solid transparent;',
  secondary: 'background: var(--surface-hover); color: var(--text); border: 1px solid var(--border-focus);',
  danger: 'background: var(--danger-bg); color: var(--danger); border: 1px solid var(--danger);',
  ghost: 'background: var(--surface-hover); color: var(--text); border: 1px solid transparent;',
};

const sizeStyles: Record<string, string> = {
  sm: 'padding: 6px 12px; font-size: 12px; border-radius: 6px;',
  md: 'padding: 8px 18px; font-size: 13px; border-radius: 8px;',
  lg: 'padding: 12px 24px; font-size: 15px; border-radius: 8px;',
};

export function Button({
  variant = 'primary',
  size = 'md',
  children,
  style,
  onMouseEnter,
  onMouseLeave,
  ...props
}: ButtonProps) {
  const [isHovered, setIsHovered] = useState(false);

  const parseStyle = (styleStr: string): [string, string][] => {
    return styleStr
      .split(';')
      .filter(Boolean)
      .map(s => {
        const colonIdx = s.indexOf(':');
        if (colonIdx === -1) return null;
        const k = s.slice(0, colonIdx).trim();
        const v = s.slice(colonIdx + 1).trim();
        if (!k || !v) return null;
        return [k.replace(/-([a-z])/g, (_, c) => c.toUpperCase()), v] as [string, string];
      })
      .filter((entry): entry is [string, string] => entry !== null);
  };

  const activeStyles = isHovered ? hoverStyles[variant] : variantStyles[variant];

  return (
    <button
      {...props}
      onMouseEnter={e => {
        setIsHovered(true);
        onMouseEnter?.(e);
      }}
      onMouseLeave={e => {
        setIsHovered(false);
        onMouseLeave?.(e);
      }}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '6px',
        fontWeight: 500,
        cursor: 'pointer',
        transition: 'all 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
        fontFamily: 'inherit',
        boxShadow: variant === 'primary' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
        ...((style as React.CSSProperties) ?? {}),
        ...(Object.fromEntries([
          ...parseStyle(activeStyles ?? ''),
          ...parseStyle(sizeStyles[size] ?? ''),
        ]) as React.CSSProperties),
      }}
    >
      {children}
    </button>
  );
}
