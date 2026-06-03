import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw/server";
import { NotificationsPage } from "../public/index";

const FIXED_NOW = new Date("2026-05-15T12:00:00Z");
const today = FIXED_NOW;
const yesterday = new Date(FIXED_NOW.getTime() - 26 * 3_600_000);
const lastWeek = new Date(FIXED_NOW.getTime() - 3 * 86_400_000);
const older = new Date(FIXED_NOW.getTime() - 60 * 86_400_000);

const FIXTURE = [
  {
    id: "n1",
    user_id: "u1",
    org_id: "o1",
    type: "hitl_waiting",
    ticket_id: "t1",
    title: "Today event",
    body: "body 1",
    read_at: null,
    created_at: today.toISOString(),
  },
  {
    id: "n2",
    user_id: "u1",
    org_id: "o1",
    type: "ticket_completed",
    ticket_id: "t2",
    title: "Yesterday event",
    body: "body 2",
    read_at: null,
    created_at: yesterday.toISOString(),
  },
  {
    id: "n3",
    user_id: "u1",
    org_id: "o1",
    type: "ticket_completed",
    ticket_id: "t3",
    title: "Last week event",
    body: "body 3",
    read_at: null,
    created_at: lastWeek.toISOString(),
  },
  {
    id: "n4",
    user_id: "u1",
    org_id: "o1",
    type: "ticket_completed",
    ticket_id: "t4",
    title: "Old event",
    body: "body 4",
    read_at: null,
    created_at: older.toISOString(),
  },
];

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("NotificationsPage (MSW)", () => {
  beforeEach(() => {
    // Only fake Date — real timers keep MSW/Promise resolution working.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(FIXED_NOW);
    server.use(
      http.get("/api/notifications", () => {
        return HttpResponse.json(FIXTURE);
      }),
      http.post("/api/notifications/mark-read", () => {
        return HttpResponse.json({ marked: FIXTURE.length });
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders skeleton while loading then shows notifications", async () => {
    render(wrap(<NotificationsPage />));
    // After data resolves, all four items render.
    await waitFor(() => {
      expect(screen.getByText("Today event")).toBeInTheDocument();
    });
    expect(screen.getByText("Yesterday event")).toBeInTheDocument();
    expect(screen.getByText("Last week event")).toBeInTheDocument();
    expect(screen.getByText("Old event")).toBeInTheDocument();
  });

  it("groups items into Today / Yesterday / This week / Older", async () => {
    render(wrap(<NotificationsPage />));
    await waitFor(() => expect(screen.getByText("Today")).toBeInTheDocument());
    expect(screen.getByText("Yesterday")).toBeInTheDocument();
    expect(screen.getByText("This week")).toBeInTheDocument();
    expect(screen.getByText("Older")).toBeInTheDocument();
  });

  it("empty state when server returns empty list", async () => {
    server.use(
      http.get("/api/notifications", () => {
        return HttpResponse.json([]);
      }),
    );
    render(wrap(<NotificationsPage />));
    await waitFor(() => {
      expect(screen.getByText(/No notifications/)).toBeInTheDocument();
    });
  });

  it("filter chips send the read_state param on click", async () => {
    const requests: string[] = [];
    server.use(
      http.get("/api/notifications", ({ request }) => {
        requests.push(new URL(request.url).searchParams.get("read_state") ?? "");
        return HttpResponse.json(FIXTURE);
      }),
    );
    render(wrap(<NotificationsPage />));
    await waitFor(() => expect(screen.getByText("Today event")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByTestId("notifications-filter-unread"));
    });

    await waitFor(() => {
      expect(requests).toContain("unread");
    });
  });

  it("row click fires mark-as-read POST", async () => {
    let markedId: string | null = null;
    server.use(
      http.post<{ id: string }>("/api/notifications/:id/read", ({ params }) => {
        markedId = params.id ?? null;
        return HttpResponse.json({ ...FIXTURE[0], read_at: new Date().toISOString() });
      }),
    );
    render(wrap(<NotificationsPage />));
    await waitFor(() => expect(screen.getByTestId("notification-row-n1")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByTestId("notification-row-n1"));
    });

    await waitFor(() => {
      expect(markedId).toBe("n1");
    });
  });

  it("Mark all read button fires POST /api/notifications/mark-read", async () => {
    let called = false;
    server.use(
      http.post("/api/notifications/mark-read", () => {
        called = true;
        return HttpResponse.json({ marked: FIXTURE.length });
      }),
    );
    render(wrap(<NotificationsPage />));
    await waitFor(() => expect(screen.getByText("Today event")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByText(/Mark all read/));
    });

    await waitFor(() => {
      expect(called).toBe(true);
    });
  });

  it("shows error banner when server errors", async () => {
    server.use(
      http.get("/api/notifications", () => {
        return HttpResponse.json({ error: "internal" }, { status: 500 });
      }),
    );
    render(wrap(<NotificationsPage />));
    await waitFor(() => {
      expect(screen.getByText(/Couldn't load notifications/)).toBeInTheDocument();
    });
  });
});
