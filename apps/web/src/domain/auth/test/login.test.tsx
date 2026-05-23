import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

/**
 * Smoke tests for the M06 Login page. Mocks `useSsoDiscover` + `useProviders`
 * and asserts the email-first flow + the per-provider fallback that e2e
 * specs depend on (`login-test` testid).
 */

const discoverMutate = vi.fn();
let discoverDataMock: { provider: "github" | "saml" } | undefined = undefined;

vi.mock("@core/api", () => ({
  useSsoDiscover: () => ({
    mutate: discoverMutate,
    isPending: false,
    data: discoverDataMock,
  }),
}));

vi.mock("../queries", () => ({
  useProviders: () => ({
    data: { providers: ["github", "test"] },
    isLoading: false,
  }),
}));

import { LoginPage } from "../LoginPage";

describe("LoginPage", () => {
  beforeEach(() => {
    discoverMutate.mockReset();
    discoverDataMock = undefined;
  });

  it("renders the email form + fallback provider buttons", () => {
    render(<LoginPage />);
    expect(screen.getByTestId("login-email")).toBeInTheDocument();
    expect(screen.getByTestId("login-continue")).toBeInTheDocument();
    expect(screen.getByTestId("login-github")).toBeInTheDocument();
    expect(screen.getByTestId("login-test")).toBeInTheDocument();
  });

  it("Continue fires useSsoDiscover.mutate with the typed email", () => {
    render(<LoginPage />);
    fireEvent.change(screen.getByTestId("login-email"), {
      target: { value: "alice@example.com" },
    });
    fireEvent.click(screen.getByTestId("login-continue"));
    expect(discoverMutate).toHaveBeenCalledWith("alice@example.com");
  });

  it("github discovery result surfaces the discovered-github button", () => {
    discoverDataMock = { provider: "github" };
    render(<LoginPage />);
    expect(screen.getByTestId("login-discovered-github")).toBeInTheDocument();
  });
});

// `beforeEach` is hoisted by Vitest when this module is run; declare for TS.
declare const beforeEach: (fn: () => void) => void;
