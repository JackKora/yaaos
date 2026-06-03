/**
 * User — Messaging.
 *
 * Placeholder route. The Messaging feature (Slack/Telegram/Email
 * destination opt-ins) is not yet built; the route exists so the User
 * popover's "Messaging" link doesn't 404.
 */

import { EmptyState } from "@shared/components/public/layout/empty-state";
import { PageHeader } from "@shared/components/public/layout/page-header";
import { MessageSquare } from "lucide-react";

export function MessagingPage() {
  return (
    <div className="mx-auto max-w-[700px] px-6 py-8">
      <PageHeader title="Messaging" subtitle="Where yaaos pings you outside the app." />
      <EmptyState
        icon={MessageSquare}
        headline="All updates land in Notifications."
        body="Today, yaaos delivers updates in Notifications. Opt-in destinations like Slack DMs, Telegram, or email digests aren't available yet."
      />
    </div>
  );
}
