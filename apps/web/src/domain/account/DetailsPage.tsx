import { Badge, Button, Card, CardContent, CardHeader } from "@shared/components";
import { useState } from "react";
import {
  type AccountOrg,
  useAccountMe,
  useClearGithubUsername,
  useUpdateDisplayName,
  useUpdateOrgHandle,
} from "./queries";

/**
 * `/account/details` — name + per-org handles + verified emails + GitHub
 * association. The verify-only GitHub flow is initiated by a regular link
 * navigation to `/api/account/github/verify` (the SPA picks it up after the
 * callback writes the username).
 */
export function DetailsPage() {
  const { data, isLoading } = useAccountMe();
  if (isLoading) return <div className="p-6">Loading…</div>;
  if (!data) {
    return (
      <div className="p-6">
        Not signed in. <a href="/login">Go to login.</a>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[900px] flex-col gap-4 p-6">
      <h1 className="text-[20px] font-semibold tracking-tight">User · Details</h1>
      <DisplayNameCard current={data.display_name} />
      <HandlesCard orgs={data.orgs} />
      <EmailsCard
        emails={data.emails.map((e) => ({
          email: e.email,
          is_primary: e.is_primary,
          verified: e.verified,
        }))}
      />
      <GithubCard username={data.github_username} />
    </div>
  );
}

function DisplayNameCard({ current }: { current: string }) {
  const [value, setValue] = useState(current);
  const update = useUpdateDisplayName();
  return (
    <Card>
      <CardHeader>
        <h2 className="text-[13.5px] font-semibold">Display name</h2>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2">
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            data-testid="display-name-input"
            className="flex-1 rounded border border-border-soft bg-bg-2 px-2 py-1 text-sm"
          />
          <Button
            data-testid="display-name-save"
            disabled={update.isPending || value === current}
            onClick={() => update.mutate(value)}
          >
            {update.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function HandlesCard({ orgs }: { orgs: AccountOrg[] }) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-[13.5px] font-semibold">Per-org handles</h2>
      </CardHeader>
      <CardContent>
        {orgs.length === 0 ? (
          <p className="text-text-3 text-xs">No org memberships yet.</p>
        ) : (
          <table className="w-full text-sm" data-testid="handles-table">
            <thead>
              <tr className="text-text-3 text-xs">
                <th className="py-1 text-left font-normal">Org</th>
                <th className="py-1 text-left font-normal">Role</th>
                <th className="py-1 text-left font-normal">Handle</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {orgs.map((o) => (
                <HandleRow key={o.org_id} org={o} />
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function HandleRow({ org }: { org: AccountOrg }) {
  const [value, setValue] = useState(org.handle);
  const update = useUpdateOrgHandle();
  const dirty = value !== org.handle;
  return (
    <tr>
      <td className="py-1.5">{org.display_name || org.slug}</td>
      <td className="py-1.5">
        <Badge variant="soft">{org.role}</Badge>
      </td>
      <td className="py-1.5">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          data-testid={`handle-input-${org.slug}`}
          className="w-[160px] rounded border border-border-soft bg-bg-2 px-2 py-1 text-sm"
        />
      </td>
      <td className="py-1.5 text-right">
        <Button
          data-testid={`handle-save-${org.slug}`}
          disabled={!dirty || update.isPending}
          onClick={() => update.mutate({ orgId: org.org_id, handle: value })}
        >
          Save
        </Button>
        {update.isError && (
          <span className="ml-2 text-[11px] text-red-500" data-testid={`handle-err-${org.slug}`}>
            {(update.error as Error)?.message || "Failed"}
          </span>
        )}
      </td>
    </tr>
  );
}

function EmailsCard({
  emails,
}: {
  emails: { email: string; is_primary: boolean; verified: boolean }[];
}) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-[13.5px] font-semibold">Emails</h2>
      </CardHeader>
      <CardContent>
        {emails.length === 0 ? (
          <p className="text-text-3 text-xs">No emails on file.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm" data-testid="emails-list">
            {emails.map((e) => (
              <li key={e.email} className="flex items-center gap-2">
                <span>{e.email}</span>
                {e.is_primary && <Badge variant="success">primary</Badge>}
                {e.verified ? (
                  <Badge variant="soft">verified</Badge>
                ) : (
                  <Badge variant="danger">unverified</Badge>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function GithubCard({ username }: { username: string | null }) {
  const clear = useClearGithubUsername();
  return (
    <Card>
      <CardHeader>
        <h2 className="text-[13.5px] font-semibold">GitHub association</h2>
      </CardHeader>
      <CardContent>
        {username ? (
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm" data-testid="github-username">
              @{username}
            </span>
            <Badge variant="success">verified</Badge>
            <a
              href="/api/account/github/verify"
              className="ml-auto rounded border border-border-soft px-2 py-1 text-xs hover:bg-hover"
              data-testid="github-reverify"
            >
              Re-verify
            </a>
            <Button
              data-testid="github-clear"
              disabled={clear.isPending}
              onClick={() => clear.mutate()}
            >
              {clear.isPending ? "Clearing…" : "Clear"}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <p className="text-text-3 text-xs">
              No GitHub handle linked. Verifying writes only your GitHub username — no identity row
              is created.
            </p>
            <a
              href="/api/account/github/verify"
              className="ml-auto rounded border border-border-soft px-2 py-1 text-xs hover:bg-hover"
              data-testid="github-connect"
            >
              Connect GitHub
            </a>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
