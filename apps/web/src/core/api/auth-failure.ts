/**
 * Central 401 handler for `apiFetch`.
 *
 * When the backend rejects a request as auth-dead (idle timeout, hard
 * expiry, or no session at all), it returns `{"error": "<reason>"}` with
 * `Set-Cookie` clears for `yaaos_session` + `yaaos_csrf` already on the
 * response. This module takes the next two steps the browser needs:
 *
 *  1. **One-time hard redirect to `/login`** with a `?reason=` query for
 *     the banner copy and a `?next=` query carrying the current path so
 *     the user lands back where they were trying to go after sign-in.
 *     `window.location.assign` (not soft-nav) is intentional — it clears
 *     React state + TanStack Query cache so stale "logged in" data
 *     doesn't keep triggering 401 cascades.
 *
 *  2. **Mutex so concurrent 401s redirect once.** Every page often fires
 *     2-3 queries in parallel (`/api/auth/me`, `/api/orgs/mine`,
 *     `/api/notifications/popover`, page-specific queries). Without a
 *     mutex, each one would call `assign` and the URL bar would race.
 *
 * `next` round-trips through `LoginPage`, which forwards it as a
 * `next=` query on `/api/auth/login?provider=...&next=...`. The backend's
 * `_safe_next` validator in `apps/backend/app/domain/sessions/web.py`
 * already rejects open-redirect attempts (must start with single `/`,
 * collapses anything else to `/`). We mirror that allowlist client-side
 * so `next` is sane before it ever hits the URL.
 */

export type AuthFailureReason = "expired" | "idle" | "signed_out";

/** Thrown from `apiFetch` after the redirect is triggered. React Query
 * sets `isError`/`data: undefined` on the calling hook; no page-level
 * component should branch on this, because the browser is about to
 * navigate away anyway. */
export class AuthError extends Error {
  constructor(public readonly reason: AuthFailureReason) {
    super(`auth_failure:${reason}`);
    this.name = "AuthError";
  }
}

/** Same-origin path allowlist mirroring backend `_safe_next`. Returns
 * the input if it's a safe relative path; null otherwise. Exported so
 * the LoginPage can validate `next` on submit without re-stating the
 * rule. */
export function safeNext(value: string | null | undefined): string | null {
  if (!value) return null;
  // Single leading `/`, no `//evil.com`, no `\\`, no scheme-relative.
  if (!value.startsWith("/")) return null;
  if (value.startsWith("//")) return null;
  if (value.includes("\\")) return null;
  // Don't loop the user back to an auth path.
  if (value === "/login" || value.startsWith("/login?") || value.startsWith("/login/")) return null;
  if (value === "/logout" || value.startsWith("/logout?") || value.startsWith("/logout/"))
    return null;
  return value;
}

/** Map the backend `{"error": <code>}` body to the UX reason the banner
 * keys off of. Backend → UX:
 *   `session_idle_expired` → `idle`
 *   `session_expired`      → `expired`
 *   `unauthenticated`      → `signed_out`
 *   anything else          → `signed_out` (catch-all so a renamed code
 *                            still produces a banner). */
export function reasonFromBody(body: unknown): AuthFailureReason {
  if (typeof body === "object" && body !== null && "error" in body) {
    const err = (body as { error: unknown }).error;
    if (err === "session_idle_expired") return "idle";
    if (err === "session_expired") return "expired";
    if (err === "unauthenticated") return "signed_out";
  }
  return "signed_out";
}

let redirectInProgress = false;

/** Test hook. Resets the once-per-page-load mutex so each `it` starts
 * with a clean state. NOT for production use. */
export function _resetAuthFailureForTests(): void {
  redirectInProgress = false;
}

/** Called from `apiFetch` on a 401. Reads the body, captures the
 * current path as `next`, hard-navigates to `/login?reason=...&next=...`.
 * Idempotent across concurrent 401s. Throws `AuthError` so callers stop
 * using the (empty) response body. */
export async function handleAuthFailure(resp: Response): Promise<never> {
  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    // Body wasn't JSON (older endpoint, network glitch). Fall through —
    // reasonFromBody returns "signed_out" as the catch-all.
  }
  const reason = reasonFromBody(body);

  if (!redirectInProgress) {
    redirectInProgress = true;
    const here = window.location.pathname + window.location.search + window.location.hash;
    const next = safeNext(here);
    const url = new URL("/login", window.location.origin);
    url.searchParams.set("reason", reason);
    if (next) url.searchParams.set("next", next);
    window.location.assign(url.toString());
  }

  throw new AuthError(reason);
}
