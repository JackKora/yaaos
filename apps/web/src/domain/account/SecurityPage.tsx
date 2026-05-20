import { apiFetch } from "@core/api";
import { useLogoutAll } from "@domain/auth";
import { Badge, Button, Card, CardContent, CardHeader } from "@shared/components";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

/**
 * `/account/security` — re-homed TOTP enrollment + sign-out-all-sessions from
 * the M02 `/account` page. Future security settings (recovery codes, passkeys,
 * hardware keys) land here.
 */
export function SecurityPage() {
  const logoutAll = useLogoutAll();
  return (
    <div className="mx-auto flex max-w-[900px] flex-col gap-4 p-6">
      <h1 className="text-[20px] font-semibold tracking-tight">User · Security</h1>
      <TotpCard />
      <Card>
        <CardHeader>
          <h2 className="text-[13.5px] font-semibold">Sessions</h2>
        </CardHeader>
        <CardContent>
          <p className="text-text-3 mb-2 text-xs">
            Sign out of every browser this account has signed in from.
          </p>
          <Button
            data-testid="logout-all"
            disabled={logoutAll.isPending}
            onClick={() =>
              logoutAll.mutate(undefined, {
                onSuccess: () => {
                  window.location.href = "/login";
                },
              })
            }
          >
            {logoutAll.isPending ? "Signing out…" : "Sign out of all sessions"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function TotpCard() {
  const [enrolled, setEnrolled] = useState<{ seed: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [verified, setVerified] = useState(false);

  const enroll = useMutation({
    mutationFn: () =>
      apiFetch<{ seed: string; otpauth_uri: string }>("/api/auth/totp/enroll", { method: "POST" }),
    onSuccess: (data) => setEnrolled(data),
  });

  const verify = useMutation({
    mutationFn: (c: string) =>
      apiFetch("/api/auth/totp/verify", {
        method: "POST",
        body: JSON.stringify({ code: c }),
      }),
    onSuccess: () => setVerified(true),
  });

  return (
    <Card>
      <CardHeader>
        <h2 className="text-[13.5px] font-semibold">Two-factor authentication</h2>
      </CardHeader>
      <CardContent>
        {!enrolled && (
          <Button
            data-testid="totp-setup"
            disabled={enroll.isPending}
            onClick={() => enroll.mutate()}
          >
            {enroll.isPending ? "Generating…" : "Set up 2FA"}
          </Button>
        )}
        {enrolled && !verified && (
          <div className="flex flex-col gap-2 text-sm">
            <p className="text-text-3 text-xs">
              Scan the QR or type the seed into your authenticator app, then enter a code.
            </p>
            <code className="mono break-all text-xs">{enrolled.otpauth_uri}</code>
            <code className="mono text-xs">{enrolled.seed}</code>
            <div className="flex gap-2">
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="6-digit code"
                className="rounded border px-2 py-1 text-sm"
                data-testid="totp-code"
              />
              <Button
                data-testid="totp-verify"
                disabled={!code || verify.isPending}
                onClick={() => verify.mutate(code)}
              >
                {verify.isPending ? "Verifying…" : "Verify"}
              </Button>
            </div>
            {verify.isError && (
              <p className="text-xs text-red-500">
                {(verify.error as Error)?.message ?? "Verify failed"}
              </p>
            )}
          </div>
        )}
        {verified && <Badge variant="success">2FA enabled</Badge>}
      </CardContent>
    </Card>
  );
}
