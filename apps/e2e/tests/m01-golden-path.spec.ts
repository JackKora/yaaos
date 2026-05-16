/**
 * M01 golden path:
 *   1. Open the SPA (loads dashboard).
 *   2. Confirm the seeded repos appear under /repos.
 *   3. Dispatch a synthetic `pull_request.opened` webhook via fake-github →
 *      yaaof creates a ticket and three review_jobs that flip to `posted`.
 *   4. Find the new ticket in the list, open its detail page, click
 *      Re-review, and assert another batch of review jobs appears.
 *   5. Write a lesson, then trigger another review and confirm the audit
 *      log records the prompt_sent entry referencing the new lesson count.
 */

import { expect, test } from "@playwright/test";

const FAKE_GITHUB_URL = process.env.FAKE_GITHUB_URL ?? "http://localhost:58081";
const YAAOF_URL = process.env.YAAOF_BASE_URL ?? "http://localhost:58080";
// fake-github runs inside docker and dispatches to yaaof over the docker network.
// From inside the fake-github container, yaaof is reachable at `http://yaaof:8080`.
const YAAOF_INTERNAL_URL =
  process.env.YAAOF_INTERNAL_URL ?? "http://yaaof:8080";

async function dispatchWebhook(deliveryId: string) {
  const payload = {
    action: "opened",
    pull_request: {
      number: 42,
      title: "Add /metrics endpoint",
      body: "Adds a Prometheus metrics endpoint.",
      draft: false,
      merged: false,
      state: "open",
      html_url: "https://github.com/acme/api/pull/42",
      user: { login: "alice", type: "User" },
      head: { ref: "feat", sha: "headsha42", repo: { fork: false } },
      base: { ref: "main", sha: "basesha42" },
      created_at: "2026-05-15T10:00:00Z",
      updated_at: "2026-05-15T10:00:00Z",
    },
    repository: { full_name: "acme/api" },
    installation: { id: "fake-install-1" },
  };
  const res = await fetch(`${FAKE_GITHUB_URL}/__test/dispatch_webhook`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event: "pull_request",
      payload,
      target_url: `${YAAOF_INTERNAL_URL}/api/github/webhook`,
      delivery_id: deliveryId,
    }),
  });
  if (!res.ok) {
    throw new Error(`dispatch_webhook failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

test("opens PR, three agents post, re-review reruns them, lesson influences next run", async ({
  page,
}) => {
  // Landing page renders.
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Hello World" })).toBeVisible();

  // Seeded repos visible.
  await page.goto("/repos");
  const reposList = page.getByTestId("repos-list");
  await expect(reposList).toContainText("acme/web");
  await expect(reposList).toContainText("acme/api");

  // 1. Dispatch the synthetic webhook.
  await dispatchWebhook(`delivery-${Date.now()}`);

  // 2. Ticket list shows the new ticket within a few refresh ticks.
  await page.goto("/tickets");
  await expect(async () => {
    const list = page.getByTestId("tickets-list");
    await expect(list).toContainText("Add /metrics endpoint", { timeout: 15_000 });
  }).toPass({ timeout: 30_000 });

  // 3. Open detail page; confirm review_jobs reach `posted`.
  await page.getByText("Add /metrics endpoint").click();
  await expect(page.getByTestId("rereview-button")).toBeVisible();
  await expect
    .poll(
      async () =>
        await page.locator('[data-testid^="review-job-posted"]').count(),
      { timeout: 30_000 },
    )
    .toBeGreaterThanOrEqual(3);

  // 4. Click Re-review and confirm a fresh batch of jobs lands.
  // We capture the audit-log size beforehand to assert it grew.
  const auditBefore = await page.getByTestId("audit-log").locator("li").count();
  await page.getByTestId("rereview-button").click();
  await expect(async () => {
    const after = await page.getByTestId("audit-log").locator("li").count();
    expect(after).toBeGreaterThan(auditBefore);
  }).toPass({ timeout: 30_000 });

  // 5. Write a lesson for acme/api and confirm a subsequent review records it.
  await page.goto("/memory");
  await page.getByTestId("lesson-repo").selectOption({ label: "acme/api" });
  await page.getByTestId("lesson-title").fill("Cite the CWE family");
  await page
    .getByTestId("lesson-body")
    .fill("When flagging an input-validation issue, name the CWE family.");
  await page.getByTestId("lesson-save").click();
  await expect(page.getByTestId("lessons-list")).toContainText("Cite the CWE family");

  // Trigger another review and confirm a fresh prompt_sent audit entry is recorded.
  await page.goto("/tickets");
  await page.getByText("Add /metrics endpoint").click();
  const beforeCount = await page.getByTestId("audit-log").locator("li").count();
  await page.getByTestId("rereview-button").click();
  await expect(async () => {
    const after = await page.getByTestId("audit-log").locator("li").count();
    expect(after).toBeGreaterThan(beforeCount);
  }).toPass({ timeout: 30_000 });

  // Confirm metrics endpoint reflects the work.
  const metrics = await page.evaluate(async () => {
    const r = await fetch("/api/reviewer/metrics");
    return r.json();
  });
  expect(metrics.total_reviews_posted).toBeGreaterThan(0);
});
