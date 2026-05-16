import {
  useRereviewMutation,
  useReviewJobsForTicket,
  useTicket,
  useTicketAudit,
  useTickets,
} from "@core/api";
import { Badge, Button, Card, CardContent, CardHeader } from "@shared/components";
import { Link, useParams } from "@tanstack/react-router";

const STATUS_VARIANT: Record<string, "success" | "danger" | "default"> = {
  posted: "success",
  failed: "danger",
};

export function TicketsPage() {
  const { data, isLoading, isError, error } = useTickets();
  return (
    <div className="mx-auto max-w-[900px]">
      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Tickets</h2>
        </CardHeader>
        <CardContent>
          {isLoading && <div className="text-text-3 text-[12.5px]">Loading…</div>}
          {isError && (
            <div className="text-danger text-[12.5px]" data-testid="tickets-error">
              {(error as Error).message}
            </div>
          )}
          {data && data.length === 0 && (
            <div className="text-text-3 text-[12.5px]" data-testid="tickets-empty">
              No tickets yet. Open a PR on a configured repo to create one.
            </div>
          )}
          <ul className="flex flex-col gap-2" data-testid="tickets-list">
            {data?.map((t) => (
              <li key={t.id} className="border border-border-soft rounded p-3 hover:bg-hover">
                <Link
                  to="/tickets/$ticketId"
                  params={{ ticketId: t.id }}
                  className="flex items-center gap-3"
                  data-testid={`ticket-row-${t.id}`}
                >
                  <Badge variant={t.status === "complete" ? "default" : "success"}>
                    {t.status}
                  </Badge>
                  <span className="font-medium text-[13px] flex-1">{t.title}</span>
                  <span className="mono text-text-4 text-[11px]">{t.source_external_id}</span>
                </Link>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

export function TicketDetailPage() {
  const { ticketId } = useParams({ from: "/tickets/$ticketId" });
  const { data: ticket } = useTicket(ticketId);
  const { data: jobs } = useReviewJobsForTicket(ticketId);
  const { data: audit } = useTicketAudit(ticketId);
  const rereview = useRereviewMutation();

  if (!ticket) {
    return <div className="mx-auto max-w-[900px] text-text-3 text-[12.5px]">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-[900px] flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-1 flex-1">
            <h2 className="font-semibold text-[14px]">{ticket.title}</h2>
            <div className="mono text-text-4 text-[11px]">
              {ticket.source_external_id} · {ticket.status}
            </div>
          </div>
          {ticket.status !== "complete" && (
            <Button
              data-testid="rereview-button"
              onClick={() => rereview.mutate(ticket.id)}
              disabled={rereview.isPending}
            >
              {rereview.isPending ? "Scheduling…" : "Re-review"}
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {ticket.description && (
            <p className="text-[12.5px] text-text-2 whitespace-pre-wrap">{ticket.description}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Agents</h2>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-col gap-2" data-testid="review-jobs">
            {jobs?.map((j) => (
              <li
                key={j.id}
                className="border border-border-soft rounded p-2.5 text-[12.5px]"
                data-testid={`review-job-${j.status}`}
              >
                <div className="flex items-center gap-2">
                  <Badge variant={STATUS_VARIANT[j.status] ?? "default"}>{j.status}</Badge>
                  <span className="mono text-text-4 text-[11px]">{j.kind}</span>
                  {j.cost_usd != null && (
                    <span className="mono text-text-4 text-[11px]">${j.cost_usd.toFixed(4)}</span>
                  )}
                </div>
                {j.findings && (j.findings as unknown[]).length > 0 && (
                  <div className="mt-1 text-text-3 text-[11.5px]">
                    {(j.findings as Array<{ title: string }>).length} finding(s)
                  </div>
                )}
              </li>
            ))}
            {jobs && jobs.length === 0 && (
              <li className="text-text-3 text-[12.5px]">No review attempts yet.</li>
            )}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Audit log</h2>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-col gap-1 text-[11.5px] mono" data-testid="audit-log">
            {audit?.map((e) => (
              <li key={e.id} className="text-text-3">
                <span className="text-text-4">
                  {new Date(e.created_at).toISOString().slice(11, 19)}
                </span>{" "}
                <span className="text-text-2">{e.kind}</span>{" "}
                <span className="text-text-4">[{e.actor.kind}]</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
