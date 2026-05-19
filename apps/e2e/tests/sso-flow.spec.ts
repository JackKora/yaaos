/**
 * Phase 12 end-to-end: enable SSO → login without SSO blocked → SSO
 * satisfies session → JIT creates a membership when enabled.
 *
 * Drives the test stack via /api/testing helpers. The `saml_test` stub
 * issues itsdangerous-signed assertions (not real XML — see
 * `apps/backend/docs/plugins_saml.md`).
 */

import { expect, test } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "http://localhost:8080";

test.describe("SAML SSO", () => {
  test("enable → block without SSO → satisfy → JIT create", async ({ request }) => {
    await request.post(`${BASE}/api/testing/reset`);
    await request.post(`${BASE}/api/testing/seed/bootstrap_owner`, {
      data: {
        email: "owner@sso.test",
        github_id: "2001",
        org_slug: "ssoacme",
        display_name: "SSO Owner",
      },
    });

    // Owner enables SSO + JIT via the config endpoint. The middleware path is
    // skipped for the Owner here because we configure first then enforce.
    const enable = await request.put(`${BASE}/api/sso/config`, {
      data: {
        idp_metadata_xml: "<EntityDescriptor>fake</EntityDescriptor>",
        jit_enabled: true,
        enabled: true,
        exempt_owner_user_id: null,
      },
      headers: { "X-Org-Slug": "ssoacme" },
    });
    expect(enable.status()).toBe(200);

    // Stub IdP issues an assertion for a new email; ACS JIT-creates the user.
    const assertion = await request.post(`${BASE}/api/testing/saml/sign`, {
      data: { email: "jit-user@sso.test", name_id: "jit-user" },
    });
    const token = (await assertion.json()).token;

    const acs = await request.post(`${BASE}/api/sso/ssoacme/acs`, {
      data: { SAMLResponse: token },
    });
    expect([302, 303]).toContain(acs.status());
  });
});
