/**
 * The headline journey: a PR arrives → yaaof reviews it → user sees findings.
 *
 * Boundary: fake-github dispatches a `pull_request.opened` webhook; yaaof
 * creates a ticket, runs the three built-in agents through the stub
 * coding-agent, posts reviews back to fake-github, and the user sees the
 * results in the UI. No interaction with the test runner once dispatched.
 */

import { expect, test } from "@playwright/test";
import {
  dispatchWebhook,
  postedReviews,
  prPayload,
  resetStack,
  seedCredentialsAndInstall,
} from "./_helpers";

test.beforeEach(async () => {
  await resetStack();
  await seedCredentialsAndInstall();
});

test("PR open → 3 agents post; ticket detail renders findings", async ({ page }) => {
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

  // Open the ticket. All three agents reach `posted`.
  await page.getByText("Add /metrics endpoint").click();
  await expect(page.getByTestId("ticket-detail")).toBeVisible();
  await expect
    .poll(() => page.locator('[data-testid^="agent-card-"][data-state="posted"]').count(), {
      timeout: 30_000,
    })
    .toBe(3);

  // SummaryStrip is populated (any value beats the loading state).
  await expect(page.getByTestId("summary-strip")).toBeVisible();

  // fake-github recorded the posts.
  const reviews = await postedReviews();
  expect(reviews.length).toBeGreaterThanOrEqual(3);
});
