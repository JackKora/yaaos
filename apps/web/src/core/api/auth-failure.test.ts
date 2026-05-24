import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  AuthError,
  _resetAuthFailureForTests,
  handleAuthFailure,
  reasonFromBody,
  safeNext,
} from "./auth-failure";

describe("safeNext", () => {
  it("accepts a same-origin relative path", () => {
    expect(safeNext("/user/details")).toBe("/user/details");
    expect(safeNext("/orgs/acme/settings/vcs")).toBe("/orgs/acme/settings/vcs");
  });

  it("rejects scheme-relative URLs", () => {
    expect(safeNext("//attacker.example.com")).toBeNull();
    expect(safeNext("//attacker.example.com/path")).toBeNull();
  });

  it("rejects absolute URLs", () => {
    expect(safeNext("https://attacker.example.com")).toBeNull();
    expect(safeNext("http://localhost:8080/")).toBeNull();
  });

  it("rejects mailto / javascript schemes", () => {
    expect(safeNext("mailto:foo@bar.com")).toBeNull();
    expect(safeNext("javascript:alert(1)")).toBeNull();
  });

  it("rejects paths containing backslashes (some browsers normalize to /)", () => {
    expect(safeNext("/foo\\..\\evil")).toBeNull();
  });

  it("rejects paths that would loop the user back to auth pages", () => {
    expect(safeNext("/login")).toBeNull();
    expect(safeNext("/login?reason=expired")).toBeNull();
    expect(safeNext("/login/oauth")).toBeNull();
    expect(safeNext("/logout")).toBeNull();
  });

  it("returns null on empty / nullish input", () => {
    expect(safeNext(null)).toBeNull();
    expect(safeNext(undefined)).toBeNull();
    expect(safeNext("")).toBeNull();
  });
});

describe("reasonFromBody", () => {
  it("maps backend error codes to UX reasons", () => {
    expect(reasonFromBody({ error: "session_idle_expired" })).toBe("idle");
    expect(reasonFromBody({ error: "session_expired" })).toBe("expired");
    expect(reasonFromBody({ error: "unauthenticated" })).toBe("signed_out");
  });

  it("falls back to signed_out for unrecognized / malformed bodies", () => {
    expect(reasonFromBody({ error: "some_future_code" })).toBe("signed_out");
    expect(reasonFromBody({})).toBe("signed_out");
    expect(reasonFromBody(null)).toBe("signed_out");
    expect(reasonFromBody("not an object")).toBe("signed_out");
  });
});

describe("handleAuthFailure", () => {
  // jsdom defaults window.location to about:blank — replace it with a
  // mockable object whose assign() is a spy we can assert against.
  let assignSpy: ReturnType<typeof vi.fn>;
  const originalLocation = window.location;

  beforeEach(() => {
    _resetAuthFailureForTests();
    assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: {
        pathname: "/user/details",
        search: "?foo=bar",
        hash: "",
        href: "http://localhost:8080/user/details?foo=bar",
        origin: "http://localhost:8080",
        assign: assignSpy,
      },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: originalLocation,
    });
  });

  function fakeResponse(body: object | null, status = 401): Response {
    return new Response(body == null ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }

  it("redirects to /login with reason + next from current path", async () => {
    await expect(
      handleAuthFailure(fakeResponse({ error: "session_idle_expired" })),
    ).rejects.toThrow(AuthError);
    expect(assignSpy).toHaveBeenCalledOnce();
    const firstCall = assignSpy.mock.calls[0];
    if (!firstCall) throw new Error("assignSpy not called");
    const navigated = new URL(firstCall[0] as string);
    expect(navigated.pathname).toBe("/login");
    expect(navigated.searchParams.get("reason")).toBe("idle");
    expect(navigated.searchParams.get("next")).toBe("/user/details?foo=bar");
  });

  it("redirects only ONCE across concurrent 401s (mutex)", async () => {
    const r = () => handleAuthFailure(fakeResponse({ error: "unauthenticated" }));
    const results = await Promise.allSettled([r(), r(), r(), r()]);
    // All four reject (callers shouldn't proceed) but window.location.assign
    // is hit exactly once.
    expect(results.every((x) => x.status === "rejected")).toBe(true);
    expect(assignSpy).toHaveBeenCalledOnce();
  });

  it("throws AuthError carrying the mapped reason", async () => {
    try {
      await handleAuthFailure(fakeResponse({ error: "session_expired" }));
      throw new Error("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(AuthError);
      expect((e as AuthError).reason).toBe("expired");
    }
  });

  it("omits ?next= when the current path would loop back to /login", async () => {
    Object.assign(window.location, { pathname: "/login", search: "", hash: "" });
    await expect(handleAuthFailure(fakeResponse({ error: "unauthenticated" }))).rejects.toThrow();
    const firstCall = assignSpy.mock.calls[0];
    if (!firstCall) throw new Error("assignSpy not called");
    const navigated = new URL(firstCall[0] as string);
    expect(navigated.searchParams.has("next")).toBe(false);
  });

  it("handles non-JSON bodies gracefully (falls back to signed_out)", async () => {
    const badResp = new Response("not json at all", { status: 401 });
    await expect(handleAuthFailure(badResp)).rejects.toMatchObject({ reason: "signed_out" });
    expect(assignSpy).toHaveBeenCalledOnce();
  });
});
