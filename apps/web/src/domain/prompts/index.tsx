import { useResetAgentPrompt, useReviewerAgents, useUpdateAgentPrompt } from "@core/api";
import { Button, Card, CardContent, CardHeader } from "@shared/components";
import { useEffect, useState } from "react";

export function PromptsPage() {
  const { data: agents } = useReviewerAgents();
  const update = useUpdateAgentPrompt();
  const reset = useResetAgentPrompt();
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    if (agents) {
      setDrafts((cur) => {
        const next = { ...cur };
        for (const a of agents) {
          if (next[a.name] === undefined) {
            next[a.name] = a.prompt_text;
          }
        }
        return next;
      });
    }
  }, [agents]);

  return (
    <div className="mx-auto max-w-[900px] flex flex-col gap-3">
      {agents?.map((a) => (
        <Card key={a.id}>
          <CardHeader>
            <h2 className="font-semibold text-[13.5px]">{a.name}</h2>
            <div className="flex-1" />
            <Button
              data-testid={`reset-${a.name}`}
              onClick={() =>
                reset.mutate(a.name, {
                  onSuccess: (fresh) => setDrafts((d) => ({ ...d, [a.name]: fresh.prompt_text })),
                })
              }
            >
              Reset to default
            </Button>
          </CardHeader>
          <CardContent>
            <textarea
              data-testid={`prompt-${a.name}`}
              value={drafts[a.name] ?? a.prompt_text}
              onChange={(e) => setDrafts((d) => ({ ...d, [a.name]: e.target.value }))}
              rows={10}
              className="w-full px-2 py-1.5 text-[12.5px] mono border border-border-soft rounded bg-bg font-mono"
            />
            <div className="flex justify-end mt-2">
              <Button
                data-testid={`save-${a.name}`}
                onClick={() => update.mutate({ name: a.name, prompt_text: drafts[a.name] ?? "" })}
                disabled={update.isPending}
              >
                Save
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
