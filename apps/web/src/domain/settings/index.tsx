import { useOnboarding, useSetAnthropicKey } from "@core/api";
import { Badge, Button, Card, CardContent, CardHeader } from "@shared/components";
import { useState } from "react";

export function SettingsPage() {
  const { data: onboarding } = useOnboarding();
  const setKey = useSetAnthropicKey();
  const [key, setKey_] = useState("");

  return (
    <div className="mx-auto max-w-[900px] flex flex-col gap-3">
      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Onboarding status</h2>
        </CardHeader>
        <CardContent>
          <ul className="text-[12.5px] flex flex-col gap-1" data-testid="onboarding-list">
            <li className="flex items-center gap-2">
              <Badge variant={onboarding?.github_app_installed ? "success" : "danger"}>
                {onboarding?.github_app_installed ? "yes" : "no"}
              </Badge>
              GitHub App installed
            </li>
            <li className="flex items-center gap-2">
              <Badge variant={onboarding?.anthropic_key_set ? "success" : "danger"}>
                {onboarding?.anthropic_key_set ? "yes" : "no"}
              </Badge>
              Anthropic key set
            </li>
            <li className="flex items-center gap-2">
              <Badge variant={onboarding?.at_least_one_repo ? "success" : "danger"}>
                {onboarding?.at_least_one_repo ? "yes" : "no"}
              </Badge>
              At least one repo allowlisted
            </li>
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Anthropic API key</h2>
        </CardHeader>
        <CardContent>
          <p className="text-text-3 text-[12px] mb-2">
            Stored encrypted-at-rest. Re-enter to rotate.
          </p>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (key.trim()) {
                setKey.mutate(key, { onSuccess: () => setKey_("") });
              }
            }}
          >
            <input
              data-testid="anthropic-key"
              type="password"
              value={key}
              onChange={(e) => setKey_(e.target.value)}
              placeholder="sk-ant-..."
              className="flex-1 px-2 py-1.5 text-[12.5px] mono border border-border-soft rounded bg-bg"
            />
            <Button type="submit" disabled={setKey.isPending} data-testid="anthropic-save">
              Save
            </Button>
          </form>
          {setKey.isSuccess && (
            <div className="text-success text-[12px] mt-1" data-testid="anthropic-saved">
              Saved.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
