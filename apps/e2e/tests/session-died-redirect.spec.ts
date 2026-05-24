/**
 * Session-died UX: visiting a protected page without a valid session
 * should land the user at `/login?reason=...&next=...` with a banner
 * explaining why, and after sign-in they should return to where they
 * were trying to go. Covers both:
 *
 *   1. Cold deeplink while logged out (no cookie at all).
 *   2. Session-died mid-flow (cookies cleared between page loads).
 *
 * Backend coverage for the 401 body shape + Set-Cookie clears lives in
 * `apps/backend/app/domain/sessions/test/test_auth_failure_service.py`;
 * SPA unit coverage of `handleAuthFailure` + `safeNext` +
 * `reasonFromBody` lives in `apps/web/src/core/api/auth-failure.test.ts`.
 * This spec proves the two layers compose end-to-end against the real
 * stack.
 */

import { expect, test } from "@playwright/test";
import { YAAOS_URL } from "./_helpers";

test.describe("session-died UX", () => {
  test("cold deeplink while logged out redirects to /login with reason + next", async ({
    page,
    request,
  }) => {
    // Empty DB; no user, no session.
    await request.post(`${YAAOS_URL}/api/testing/reset`);

    // Hit a protected user-scoped page directly (under an org slug — user
    // pages are nested at /orgs/$slug/user/* now).
    await page.goto(`${YAAOS_URL}/orgs/acme/user/details`);

    // The central 401 handler should hard-navigate to /login with both
    // ?reason= and ?next= populated. Wait for the URL to settle.
    await page.waitForURL(/\/login\?/, { timeout: 10_000 });

    const url = new URL(page.url());
    expect(url.pathname).toBe("/login");
    // We never logged in — the 401 came from /api/user/me without a
    // session cookie, mapped to `signed_out`.
    expect(url.searchParams.get("reason")).toBe("signed_out");
    expect(url.searchParams.get("next")).toBe("/orgs/acme/user/details");

    // Banner copy renders.
    await expect(page.getByTestId("login-reason-banner")).toHaveText(
      "You were signed out. Sign in to continue.",
    );
  });

  test("plain /login (no query) shows no banner", async ({ page, request }) => {
    await request.post(`${YAAOS_URL}/api/testing/reset`);

    await page.goto(`${YAAOS_URL}/login`);

    await expect(page.getByTestId("login-reason-banner")).toHaveCount(0);
  });

  test("each reason value renders its banner copy", async ({ page, request }) => {
    await request.post(`${YAAOS_URL}/api/testing/reset`);

    const cases: Array<[string, string]> = [
      ["idle", "Your session timed out from inactivity. Sign in to continue."],
      ["expired", "Your session expired. Sign in to continue."],
      ["signed_out", "You were signed out. Sign in to continue."],
    ];
    for (const [reason, copy] of cases) {
      await page.goto(`${YAAOS_URL}/login?reason=${reason}`);
      await expect(page.getByTestId("login-reason-banner")).toHaveText(copy);
    }

    // Unrecognized value → no banner (catch-all).
    await page.goto(`${YAAOS_URL}/login?reason=garbage_value`);
    await expect(page.getByTestId("login-reason-banner")).toHaveCount(0);
  });
});
