/**
 * Tests for core/observability ErrorBoundary:
 * - When a child throws and fallbackRender is NOT supplied, the default fallback renders.
 * - When a child throws and fallbackRender IS supplied, the custom fallback renders AND
 *   recordException is still called (OTel wiring is intact).
 */

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "../public/error-boundary";
import { _resetObservabilityForTests } from "../public/sdk";

// Suppress React's noisy "The above error occurred in the <Bomb> component" console.error
// so test output stays readable.
const _consoleError = console.error;
beforeEach(() => {
  console.error = vi.fn();
});
afterEach(() => {
  console.error = _consoleError;
  _resetObservabilityForTests();
});

function Bomb({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("test render crash");
  return <div>safe content</div>;
}

describe("ErrorBoundary — default fallback (no fallbackRender prop)", () => {
  it("renders the default 'Something went wrong' fallback when a child throws", () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
  });

  it("renders children normally when nothing throws", () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("safe content")).toBeInTheDocument();
  });
});

describe("ErrorBoundary — custom fallbackRender prop", () => {
  it("renders the custom fallback instead of the default when fallbackRender is supplied", () => {
    render(
      <ErrorBoundary
        fallbackRender={({ error }) => (
          <div data-testid="custom-fallback">custom: {(error as Error).message}</div>
        )}
      >
        <Bomb shouldThrow />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
    expect(screen.getByText(/custom: test render crash/i)).toBeInTheDocument();
    // The default fallback must NOT be rendered
    expect(screen.queryByText(/Something went wrong/i)).not.toBeInTheDocument();
  });

  it("calls recordException when a child throws and fallbackRender is supplied", async () => {
    const sdkModule = await import("../public/sdk");
    const recordSpy = vi.spyOn(sdkModule, "recordException");

    render(
      <ErrorBoundary
        fallbackRender={({ resetErrorBoundary }) => (
          <button type="button" onClick={resetErrorBoundary} data-testid="retry">
            retry
          </button>
        )}
      >
        <Bomb shouldThrow />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("retry")).toBeInTheDocument();
    expect(recordSpy).toHaveBeenCalledOnce();
    const firstCall = recordSpy.mock.calls[0];
    expect(firstCall).toBeDefined();
    if (firstCall) {
      const callArg = firstCall[0];
      expect(callArg).toBeInstanceOf(Error);
      expect((callArg as Error).message).toBe("test render crash");
    }

    recordSpy.mockRestore();
  });

  it("resetErrorBoundary resets the boundary so the child re-renders", async () => {
    let shouldThrow = true;

    const { rerender } = render(
      <ErrorBoundary
        fallbackRender={({ resetErrorBoundary }) => (
          <button
            type="button"
            onClick={() => {
              shouldThrow = false;
              resetErrorBoundary();
            }}
            data-testid="retry"
          >
            retry
          </button>
        )}
      >
        {/* Re-render with new shouldThrow after resetErrorBoundary is called */}
        <Bomb shouldThrow={shouldThrow} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("retry")).toBeInTheDocument();

    // Click retry → resetErrorBoundary triggers re-render
    screen.getByTestId("retry").click();

    rerender(
      <ErrorBoundary
        fallbackRender={({ resetErrorBoundary }) => (
          <button
            type="button"
            onClick={() => {
              shouldThrow = false;
              resetErrorBoundary();
            }}
            data-testid="retry"
          >
            retry
          </button>
        )}
      >
        <Bomb shouldThrow={shouldThrow} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("safe content")).toBeInTheDocument();
  });
});
