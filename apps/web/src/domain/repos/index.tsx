import { useAddRepo, useRemoveRepo, useRepos } from "@core/api";
import { Badge, Button, Card, CardContent, CardHeader } from "@shared/components";
import { useState } from "react";

export function ReposPage() {
  const { data } = useRepos();
  const add = useAddRepo();
  const remove = useRemoveRepo();
  const [external, setExternal] = useState("");

  return (
    <div className="mx-auto max-w-[900px] flex flex-col gap-3">
      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Allowed repositories</h2>
        </CardHeader>
        <CardContent>
          <form
            className="flex gap-2 mb-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (external.trim()) {
                add.mutate(external.trim(), { onSuccess: () => setExternal("") });
              }
            }}
          >
            <input
              data-testid="repo-input"
              value={external}
              onChange={(e) => setExternal(e.target.value)}
              placeholder="owner/repo"
              className="flex-1 px-2 py-1.5 text-[12.5px] border border-border-soft rounded bg-bg"
            />
            <Button type="submit" data-testid="repo-add" disabled={add.isPending}>
              Add
            </Button>
          </form>
          {add.isError && (
            <div className="text-danger text-[12px] mb-2" data-testid="repo-error">
              {(add.error as Error).message}
            </div>
          )}
          <ul className="flex flex-col gap-1" data-testid="repos-list">
            {data?.map((r) => (
              <li
                key={r.id}
                className="flex items-center gap-2 border border-border-soft rounded px-2 py-1.5"
              >
                <Badge variant="success">{r.status}</Badge>
                <span className="mono text-[12.5px] flex-1">{r.external_id}</span>
                {r.language_hint && (
                  <span className="mono text-text-4 text-[11px]">{r.language_hint}</span>
                )}
                <button
                  type="button"
                  className="text-text-4 hover:text-danger text-[11px]"
                  onClick={() => remove.mutate(r.id)}
                >
                  Remove
                </button>
              </li>
            ))}
            {data && data.length === 0 && (
              <li className="text-text-3 text-[12.5px]">No repos yet.</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
