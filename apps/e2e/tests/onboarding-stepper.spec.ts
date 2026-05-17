/**
 * Empty-DB → fully-onboarded.
 *
 * Boundary: the user lands on /dashboard with nothing configured, walks the
 * stepper end-to-end (GitHub credentials + Anthropic API key), and the
 * dashboard flips to its populated state. No webhook traffic in this spec —
 * subsequent specs cover the review pipeline.
 *
 * Uses the credentials-paste escape hatch on the Settings card rather than
 * the Manifest flow (the Manifest UI is a real github.com redirect and can't
 * be e2e'd against fake-github).
 */

import { expect, test } from "@playwright/test";
import { dispatchWebhook, resetStack } from "./_helpers";

test.beforeEach(async () => {
  await resetStack();
});

test("operator completes onboarding from an empty DB", async ({ page }) => {
  // 1. Dashboard renders the onboarding stepper.
  await page.goto("/dashboard");
  await expect(page.getByTestId("dashboard-onboarding")).toBeVisible();
  await expect(page.getByTestId("onboarding-progress")).toContainText("0 of");

  // 2. Step 1: GitHub credentials via the escape-hatch form.
  await page.goto("/settings");
  // Expand the manual credentials form (only visible in the "no app" state).
  await page.getByText("Already have an App? Enter it manually").click();
  await page.getByTestId("gh-app-id").fill("12345");
  await page.getByTestId("gh-slug").fill("yaaos-test");
  await page
    .getByTestId("gh-pem")
    .fill(
      "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Q\n-----END RSA PRIVATE KEY-----",
    );
  await page.getByTestId("gh-webhook-secret").fill("TEST-FAKE-NOT-FOR-PROD-aaaaaaaaaaaaaaaa");
  await page.getByTestId("gh-save").click();
  // Form unmounts on save; the card flips to "app created · not installed".
  await expect(page.getByTestId("github-status")).toContainText("app created", {
    timeout: 10_000,
  });

  // 3. Simulate the operator installing the App on GitHub: in real life
  // they click through to github.com which fires `installation.created`
  // back to yaaos. We dispatch the webhook directly — fake-github HMAC-signs
  // it with the secret yaaos just saved.
  await dispatchWebhook({
    event: "installation",
    payload: {
      action: "created",
      installation: { id: "fake-install-1", account: { login: "acme" } },
    },
  });

  // 4. Step 2: Anthropic API key on the same Settings page (no gating between
  // cards — the user can fill them in any order).
  await page.getByTestId("anthropic-key").fill("sk-ant-test-not-real-key-eeeeeeeeeeeeeeeeeeeeee");
  await page.getByTestId("anthropic-save").click();
  await expect(page.getByTestId("anthropic-saved")).toBeVisible();
  await expect(page.getByTestId("apikey-status")).toContainText("configured");

  // 5. Dashboard now renders the populated state.
  await page.goto("/dashboard");
  await expect(page.getByTestId("dashboard-populated")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("dashboard-metrics")).toBeVisible();
});
