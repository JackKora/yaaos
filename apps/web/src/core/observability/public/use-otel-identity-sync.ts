/**
 * Syncs authenticated identity into the OTel identity holder.
 *
 * Uses `apiFetch<CurrentUser>` (typed, centralized auth handling) to fetch
 * `/api/auth/me`. On success, calls `setIdentity` with org slug + user id.
 * On 401, `apiFetch` throws `AuthError` and hard-redirects to `/login` via
 * `handleAuthFailure` — identity is cleared. On any other error (503, network
 * failure), identity is left intact and the error is recorded via
 * `recordException`. Re-runs when the org slug derived from the URL changes.
 */

import { AuthError } from "@core/api/public/auth-failure";
import { apiFetch } from "@core/api/public/client";
import { getCurrentOrgSlug } from "@core/api/public/org-context";
import type { CurrentUser } from "@core/api/public/queries";
import { useEffect } from "react";
import { setIdentity } from "../identity";
import { recordException } from "./sdk";

/**
 * Call once in AppShell. Re-runs when the org slug in the URL changes.
 * Clears identity only on 401 (AuthError from apiFetch). Leaves identity
 * intact and records the error on transient failures (5xx, network errors).
 */
export function useOtelIdentitySync(): void {
  const orgSlug = getCurrentOrgSlug();

  useEffect(() => {
    let cancelled = false;

    apiFetch<CurrentUser>("/api/auth/me")
      .then((body) => {
        if (cancelled) return;
        setIdentity(orgSlug ? { orgId: orgSlug, userId: body.user.id } : null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof AuthError) {
          // 401: apiFetch already triggered a hard redirect to /login.
          // Clear identity so stale span attributes don't persist.
          setIdentity(null);
        } else {
          // Transient error (5xx, network failure): leave identity intact.
          // The user is still authenticated; a momentary outage shouldn't
          // blank their org context on in-flight spans.
          recordException(err);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [orgSlug]);
}
