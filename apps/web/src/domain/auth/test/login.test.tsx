import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetObservabilityForTests } from "../../../core/observability/public/sdk";
import { server } from "../../../test/msw/server";
import { LoginPage } from "../public/LoginPage";

/**
 * Smoke tests for the Login page. Uses MSW to intercept:
 *   - GET /api/auth/providers — controls which provider buttons render.
 *   - POST /api/sso/discover — controls the SSO discovery flow.
 *
 * Asserts:
 *   - the top-level "Sign in with GitHub" button renders when github is configured.
 *   - the email-first SAML discovery flow renders the discovered button.
 *   - the test stub provider surfaces in the "Other" section.
 *   - a providers-fetch render error shows the retry fallback and calls recordException.
 */

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

// Suppress React error boundary console noise in the error-boundary test.
const _consoleError = console.error;

describe("LoginPage (MSW)", () => {
  it("renders a top-level Sign in with GitHub button without typing an email", async () => {
    server.use(
      http.get("/api/auth/providers", () => HttpResponse.json({ providers: ["github", "test"] })),
    );
    render(wrap(<LoginPage />));
    await waitFor(() => expect(screen.getByTestId("login-github")).toBeInTheDocument());
    expect(screen.getByTestId("login-email")).toBeInTheDocument();
    expect(screen.getByTestId("login-continue")).toBeInTheDocument();
    expect(screen.getByTestId("login-test")).toBeInTheDocument();
  });

  it("Continue fires the SSO discover mutation and surfaces the SAML button", async () => {
    server.use(
      http.get("/api/auth/providers", () => HttpResponse.json({ providers: ["github"] })),
      http.get("/api/sso/discover", () =>
        HttpResponse.json({
          provider: "saml" as const,
          saml_idp_name: "Okta",
          saml_org_slug: "acme",
        }),
      ),
    );
    render(wrap(<LoginPage />));
    await waitFor(() => expect(screen.getByTestId("login-github")).toBeInTheDocument());

    await act(async () => {
      fireEvent.change(screen.getByTestId("login-email"), {
        target: { value: "alice@example.com" },
      });
      fireEvent.click(screen.getByTestId("login-continue"));
    });

    await waitFor(() => {
      expect(screen.getByTestId("login-discovered-saml")).toBeInTheDocument();
    });
  });

  it("no providers configured shows the fallback message", async () => {
    server.use(http.get("/api/auth/providers", () => HttpResponse.json({ providers: [] })));
    render(wrap(<LoginPage />));
    await waitFor(() =>
      expect(screen.getByText(/No identity providers configured/i)).toBeInTheDocument(),
    );
  });
});

describe("LoginPage — ErrorBoundary wiring (core OTel boundary)", () => {
  beforeEach(() => {
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = _consoleError;
    _resetObservabilityForTests();
  });

  it("shows the retry ErrorBanner and calls recordException when the providers fetch throws", async () => {
    // Force the providers endpoint to error so the Suspense/ErrorBoundary subtree throws.
    server.use(http.get("/api/auth/providers", () => HttpResponse.error()));

    const sdkModule = await import("../../../core/observability/public/sdk");
    const recordSpy = vi.spyOn(sdkModule, "recordException");

    render(wrap(<LoginPage />));

    // The ErrorBoundary fallbackRender shows "Couldn't load sign-in options."
    await waitFor(() =>
      expect(screen.getByText(/Couldn't load sign-in options/i)).toBeInTheDocument(),
    );

    // The retry button is rendered (ErrorBanner with onRetry)
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();

    // recordException must have been called — the core OTel boundary is wired
    expect(recordSpy).toHaveBeenCalled();

    recordSpy.mockRestore();
  });
});
