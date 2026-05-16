/**
 * Settings cards have no cross-card gating.
 *
 * Boundary: with nothing configured, the Anthropic key card accepts a save
 * (no "you need GitHub first" gate). After saving the key, the GitHub card
 * still works for credentials paste. Plugin health card renders one row per
 * known plugin without erroring.
 */

import { expect, test } from "@playwright/test";
import { resetStack } from "./_helpers";

test.beforeEach(async () => {
  await resetStack();
});

test("Anthropic and GitHub cards save independently", async ({ page }) => {
  await page.goto("/settings");

  // Save Anthropic first, even though GitHub isn't configured.
  await page.getByTestId("anthropic-key").fill("sk-ant-test-not-real-key-eeeeeeeeeeeeeeeeeeeeee");
  await page.getByTestId("anthropic-save").click();
  await expect(page.getByTestId("anthropic-saved")).toBeVisible();
  await expect(page.getByTestId("apikey-status")).toContainText("configured");

  // GitHub card still works for credential entry — no gate.
  await page.getByText("Already have an App? Enter it manually").click();
  await page.getByTestId("gh-app-id").fill("12345");
  await page.getByTestId("gh-slug").fill("yaaof-test");
  await page
    .getByTestId("gh-pem")
    .fill(
      "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Q\n-----END RSA PRIVATE KEY-----",
    );
  await page.getByTestId("gh-webhook-secret").fill("TEST-FAKE-NOT-FOR-PROD-aaaaaaaaaaaaaaaa");
  await page.getByTestId("gh-save").click();
  // On success the card switches from "no app" to "app created · not
  // installed" — the form unmounts so we assert on the status badge.
  await expect(page.getByTestId("github-status")).toContainText("app created", {
    timeout: 10_000,
  });

  // Plugin health card renders rows without throwing.
  await expect(page.getByTestId("plugin-health-list")).toBeVisible();
});
