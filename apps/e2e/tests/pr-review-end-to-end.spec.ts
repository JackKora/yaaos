/**
 * The headline journey: a PR arrives → yaaos reviews it → user sees findings.
 *
 * Boundary: fake-github dispatches a `pull_request.opened` webhook; yaaos
 * creates a ticket, runs one review (the parent reviewer dispatches yaaos-*
 * subagents internally; the stub coding-agent short-circuits the CLI),
 * posts one Review back to fake-github, and the user sees the results in
 * the UI. No interaction with the test runner once dispatched.
 */

import { expect, test } from "@playwright/test";
import {
  dispatchWebhook,
  postedComments,
  prPayload,
  resetStack,
  seedCredentialsAndInstall,
} from "./_helpers";

test.beforeEach(async () => {
  await resetStack();
  await seedCredentialsAndInstall();
});

test("PR open → reviewer posts; ticket detail renders findings", async ({ page }) => {
  await dispatchWebhook({
    event: "pull_request",
    payload: prPayload({
      repo: "acme/api",
      number: 42,
      title: "Add /metrics endpoint",
      body: "Adds a Prometheus metrics endpoint.",
    }),
  });

  // Ticket appears in the list within a few SSE/polling ticks.
  await page.goto("/tickets");
  await expect(page.getByTestId("tickets-list")).toContainText("Add /metrics endpoint", {
    timeout: 20_000,
  });

  // Open the ticket. The review reaches `posted`.
  await page.getByText("Add /metrics endpoint").click();
  await expect(page.getByTestId("ticket-detail")).toBeVisible();
  await expect
    .poll(() => page.locator('[data-testid^="agent-card-"][data-state="posted"]').count(), {
      timeout: 30_000,
    })
    .toBe(1);

  // SummaryStrip is populated (any value beats the loading state).
  await expect(page.getByTestId("summary-strip")).toBeVisible();

  // fake-github recorded the post.
  const comments = await postedComments();
  expect(comments.length).toBeGreaterThanOrEqual(1);
});

/**
 * SSE-driven state transitions: open ticket-detail before the review starts;
 * the review-card flips to `posted` WITHOUT a manual reload (the contract
 * `review_job_status_changed` events drive in `apps/web`).
 *
 * Folded in from the standalone `sse-step-progress-live.spec.ts` so we
 * don't pay the docker-compose bring-up twice for the same backend flow.
 */
test("review card state transitions live via SSE without reload", async ({ page }) => {
  // Land on the tickets list FIRST so the SSE subscriber is mounted before
  // any events fly.
  await page.goto("/tickets");
  await dispatchWebhook({
    event: "pull_request",
    payload: prPayload({ repo: "acme/web", number: 55, title: "Live SSE check" }),
  });
  await expect(page.getByText("Live SSE check")).toBeVisible({ timeout: 20_000 });
  await page.getByText("Live SSE check").click();
  // Terminal `posted` state arrives via SSE without a page reload.
  await expect
    .poll(() => page.locator('[data-testid^="agent-card-"][data-state="posted"]').count(), {
      timeout: 30_000,
    })
    .toBe(1);
});
