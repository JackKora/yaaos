/**
 * Root error boundary for the yaaos SPA.
 *
 * Wraps the application tree; any unhandled render error calls recordException
 * on the active OTel span (or opens a short-lived span) and renders a
 * user-facing fallback. Uses react-error-boundary as the implementation so
 * the component itself stays a simple function wrapper.
 */

import type React from "react";
import { type FallbackProps, ErrorBoundary as ReactErrorBoundary } from "react-error-boundary";
import { recordException } from "./sdk";

function DefaultFallback({ error }: FallbackProps): React.ReactElement {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="p-8 text-foreground">
      <h1 className="mb-2 text-lg font-semibold">Something went wrong.</h1>
      <p className="text-muted-foreground text-sm">{message}</p>
    </div>
  );
}

function handleError(error: unknown): void {
  recordException(error);
}

type Props = {
  children: React.ReactNode;
  /**
   * Optional custom fallback renderer. Receives `{ error, resetErrorBoundary }`.
   * When supplied, replaces the default "Something went wrong" fallback.
   * `recordException` (OTel) is still called regardless.
   */
  fallbackRender?: (props: FallbackProps) => React.ReactElement;
};

export function ErrorBoundary({ children, fallbackRender }: Props): React.ReactElement {
  // react-error-boundary allows only ONE of FallbackComponent / fallbackRender / fallback.
  // Use fallbackRender when the caller provides a custom renderer; otherwise use the
  // default FallbackComponent so existing callers are unaffected.
  if (fallbackRender) {
    return (
      <ReactErrorBoundary fallbackRender={fallbackRender} onError={handleError}>
        {children}
      </ReactErrorBoundary>
    );
  }
  return (
    <ReactErrorBoundary FallbackComponent={DefaultFallback} onError={handleError}>
      {children}
    </ReactErrorBoundary>
  );
}
