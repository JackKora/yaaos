import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type React from "react";
import { Suspense } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../../../test/msw/server";
import { RequireMembership } from "../public/RequireMembership";

function meResp(role: "owner" | "admin" | "builder" | null) {
  return {
    user: { id: "u1", display_name: "Jane", primary_email: "j@x.test", emails: [] },
    memberships:
      role === null
        ? []
        : [{ org_id: "o1", slug: "acme", display_name: "Acme", role, handle: "jane" }],
  };
}

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <Suspense fallback={null}>{node}</Suspense>
    </QueryClientProvider>
  );
}

describe("RequireMembership", () => {
  beforeEach(() => {
    server.use(http.get("/api/auth/me", () => HttpResponse.json(meResp("admin"))));
  });

  it("renders children when the user meets the required role", async () => {
    render(
      wrap(
        <RequireMembership orgSlug="acme" minRole="admin">
          <span>gated</span>
        </RequireMembership>,
      ),
    );
    await waitFor(() => expect(screen.getByText("gated")).toBeInTheDocument());
  });

  it("renders the fallback when the user's role is insufficient", async () => {
    server.use(http.get("/api/auth/me", () => HttpResponse.json(meResp("builder"))));
    render(
      wrap(
        <RequireMembership orgSlug="acme" minRole="admin" fallback={<span>nope</span>}>
          <span>gated</span>
        </RequireMembership>,
      ),
    );
    await waitFor(() => expect(screen.getByText("nope")).toBeInTheDocument());
    expect(screen.queryByText("gated")).not.toBeInTheDocument();
  });

  it("renders the fallback when the user has no membership in the org", async () => {
    server.use(http.get("/api/auth/me", () => HttpResponse.json(meResp(null))));
    render(
      wrap(
        <RequireMembership orgSlug="acme" minRole="builder" fallback={<span>nope</span>}>
          <span>gated</span>
        </RequireMembership>,
      ),
    );
    await waitFor(() => expect(screen.getByText("nope")).toBeInTheDocument());
    expect(screen.queryByText("gated")).not.toBeInTheDocument();
  });
});
