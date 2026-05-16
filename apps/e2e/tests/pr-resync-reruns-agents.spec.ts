/**
 * `pull_request.synchronize` after an initial review reruns the three agents.
 *
 * Also lightly covers the force-push detection wire — the synchronize handler
 * always calls fake-github's `/compare` endpoint. We seed `status=diverged`
 * for the second push to make sure the call path succeeds end-to-end.
 *
 * Boundary: webhook → ticket exists → re-run → audit log grows.
 */

import { expect, test } from "@playwright/test";
import {
  dispatchWebhook,
  postedReviews,
  prPayload,
  resetStack,
  seedCompareDiverged,
  seedCredentialsAndInstall,
} from "./_helpers";

test.beforeEach(async () => {
  await resetStack();
  await seedCredentialsAndInstall();
});

test("synchronize event re-runs reviewers and grows the audit log", async ({ page }) => {
  const opened = prPayload({
    repo: "acme/api",
    number: 7,
    title: "Refactor request pipeline",
  });
  await dispatchWebhook({ event: "pull_request", payload: opened });

  await page.goto("/tickets");
  await page.getByText("Refactor request pipeline").click();
  await expect
    .poll(() => page.locator('[data-testid^="agent-card-"][data-state="posted"]').count(), {
      timeout: 30_000,
    })
    .toBe(3);

  const reviewsBefore = (await postedReviews()).length;

  // Second push — declare it diverged, simulating a force-push.
  const beforeSha = "head-acme-api-7";
  const afterSha = "head-acme-api-7-v2";
  await seedCompareDiverged(beforeSha, afterSha);
  await dispatchWebhook({
    event: "pull_request",
    payload: prPayload({
      repo: "acme/api",
      number: 7,
      title: "Refactor request pipeline",
      action: "synchronize",
      before: beforeSha,
      after: afterSha,
      headSha: afterSha,
    }),
  });

  // Poll fake-github for the second batch of posts — the synchronize batch
  // reruns the three agents, so the count should hit reviewsBefore + 3.
  await expect
    .poll(async () => (await postedReviews()).length, { timeout: 30_000 })
    .toBeGreaterThan(reviewsBefore);

  // Audit log also grew (initial batch wrote 3 jobs × ~3 entries each, plus
  // the synchronize batch).
  await page.getByTestId("tab-audit").click();
  await expect(page.getByTestId("audit-log").locator("li").nth(9)).toBeVisible({
    timeout: 10_000,
  });
});
