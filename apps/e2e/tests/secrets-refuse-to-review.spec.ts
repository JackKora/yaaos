/**
 * Pre-flight secrets check refuses to review and posts a single warning.
 *
 * Boundary: a PR whose diff contains an AWS-access-key-shaped string arrives;
 * all three agents transition to `skipped(secrets_detected)`; fake-github
 * received at least one refuse-to-review comment.
 */

import { expect, test } from "@playwright/test";
import {
  dispatchWebhook,
  postedReviews,
  prPayload,
  resetStack,
  seedCredentialsAndInstall,
  seedPRDiff,
} from "./_helpers";

test.beforeEach(async () => {
  await resetStack();
  await seedCredentialsAndInstall();
});

test("PR with secret in diff is refused; agents skip", async ({ page }) => {
  await seedPRDiff({
    repo: "acme/api",
    number: 99,
    diff: [
      "diff --git a/.env b/.env",
      "+++ b/.env",
      "+AWS_KEY=AKIAIOSFODNN7EXAMPLE",
    ].join("\n"),
    files: [{ filename: ".env", status: "modified", additions: 1, deletions: 0 }],
  });
  await dispatchWebhook({
    event: "pull_request",
    payload: prPayload({
      repo: "acme/api",
      number: 99,
      title: "Add env file with credentials",
    }),
  });

  await page.goto("/tickets");
  await page.getByText("Add env file with credentials").click();

  // All three agents reach `skipped` (none should reach `posted`).
  await expect
    .poll(() => page.locator('[data-testid^="agent-card-"][data-state="skipped"]').count(), {
      timeout: 30_000,
    })
    .toBe(3);
  await expect(
    page.locator('[data-testid^="agent-card-"][data-state="posted"]'),
  ).toHaveCount(0);

  // fake-github received the refuse-to-review review(s).
  const reviews = await postedReviews();
  const refusalBodies = reviews.map((r) => String(r.body ?? ""));
  expect(refusalBodies.some((b) => b.toLowerCase().includes("secret"))).toBe(true);
});
