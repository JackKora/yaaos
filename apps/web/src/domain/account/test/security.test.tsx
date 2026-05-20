import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@domain/auth", () => ({
  useLogoutAll: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("@core/api", () => ({
  apiFetch: vi.fn(),
}));

import { SecurityPage } from "../SecurityPage";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("SecurityPage", () => {
  it("shows the TOTP setup button and logout-all action", () => {
    render(wrap(<SecurityPage />));
    expect(screen.getByTestId("totp-setup")).toBeInTheDocument();
    expect(screen.getByTestId("logout-all")).toBeInTheDocument();
  });
});
