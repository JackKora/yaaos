import { useCreateLesson, useDeleteLesson, useLessons, useRepos } from "@core/api";
import { Button, Card, CardContent, CardHeader } from "@shared/components";
import { useState } from "react";

export function MemoryPage() {
  const { data: lessons } = useLessons();
  const { data: repos } = useRepos();
  const create = useCreateLesson();
  const remove = useDeleteLesson();

  const [repoId, setRepoId] = useState<string>("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  return (
    <div className="mx-auto max-w-[900px] flex flex-col gap-3">
      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Add a lesson</h2>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (!repoId || !title.trim() || !body.trim()) return;
              create.mutate(
                { repo_id: repoId, title: title.trim(), body: body.trim() },
                {
                  onSuccess: () => {
                    setTitle("");
                    setBody("");
                  },
                },
              );
            }}
          >
            <select
              data-testid="lesson-repo"
              value={repoId}
              onChange={(e) => setRepoId(e.target.value)}
              className="px-2 py-1.5 text-[12.5px] border border-border-soft rounded bg-bg"
            >
              <option value="">(select a repo)</option>
              {repos?.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.external_id}
                </option>
              ))}
            </select>
            <input
              data-testid="lesson-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="title"
              className="px-2 py-1.5 text-[12.5px] border border-border-soft rounded bg-bg"
            />
            <textarea
              data-testid="lesson-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="body (≤1000 chars)"
              maxLength={1000}
              rows={3}
              className="px-2 py-1.5 text-[12.5px] border border-border-soft rounded bg-bg"
            />
            <Button type="submit" data-testid="lesson-save" disabled={create.isPending}>
              Save
            </Button>
            {create.isError && (
              <div className="text-danger text-[12px]" data-testid="lesson-error">
                {(create.error as Error).message}
              </div>
            )}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Lessons</h2>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-col gap-2" data-testid="lessons-list">
            {lessons?.map((l) => (
              <li key={l.id} className="border border-border-soft rounded p-2.5 text-[12.5px]">
                <div className="flex items-center gap-2">
                  <span className="font-medium flex-1">{l.title}</span>
                  <button
                    type="button"
                    className="text-text-4 hover:text-danger text-[11px]"
                    onClick={() => remove.mutate(l.id)}
                  >
                    Delete
                  </button>
                </div>
                <p className="text-text-3 mt-1 whitespace-pre-wrap">{l.body}</p>
              </li>
            ))}
            {lessons && lessons.length === 0 && (
              <li className="text-text-3 text-[12.5px]">No lessons yet.</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
