'use client';

import { Component, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * ErrorBoundary — catches React rendering errors in child components.
 *
 * CRITICAL FIX (vs original architecture):
 * Without error boundaries, a crash in any panel (editor, variables,
 * explanations) would take down the entire page. Now each panel is
 * isolated — one crash doesn't affect the others.
 *
 * Usage:
 *   <ErrorBoundary fallback={<FallbackUI />}>
 *     <SomeRiskyComponent />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to console in dev, send to Sentry in prod
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  resetError = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            padding: '40px',
            background: '#0d1117',
            color: '#8b949e',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '32px', marginBottom: '16px' }}>⚠</div>
          <h3 style={{ color: '#f85149', marginBottom: '8px', fontSize: '16px' }}>
            Something went wrong
          </h3>
          <p style={{ fontSize: '13px', maxWidth: '400px', marginBottom: '16px' }}>
            {this.state.error?.message || 'An unexpected error occurred in this component.'}
          </p>
          <button
            onClick={this.resetError}
            style={{
              padding: '8px 16px',
              background: '#21262d',
              border: '1px solid #30363d',
              borderRadius: '6px',
              color: '#e6edf3',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Panel-specific error boundaries — wrap each major panel with one.
 */
export function EditorErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      fallback={
        <div
          style={{
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#0d1117',
            color: '#484f58',
            fontSize: '13px',
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>📝</div>
            <p>Code editor encountered an error</p>
          </div>
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  );
}

export function VariablePanelErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      fallback={
        <div
          style={{
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#0d1117',
            color: '#484f58',
            fontSize: '13px',
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>📊</div>
            <p>Variable panel encountered an error</p>
          </div>
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  );
}

export function ExplanationPanelErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      fallback={
        <div
          style={{
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#0d1117',
            color: '#484f58',
            fontSize: '13px',
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>💡</div>
            <p>Explanation panel encountered an error</p>
          </div>
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  );
}
