/** Server-sent event from yaaof's `/api/events` stream.
 *
 * The backend's `Event` base class (see `app/core/events/service.py`) emits:
 * - `kind`: discriminator (e.g. "ticket_status_changed", "review_job_status_changed")
 * - `source_module`: which domain module published
 * - `ts`: ISO timestamp
 * - `ticket_id`: optional, used for filtered subscriptions
 *
 * Subclasses add extra fields (e.g. ReviewJobStatusChanged adds review_job_id,
 * agent_id, status). The FE treats the payload as opaque except for `kind`
 * and `ticket_id` — translation to cache invalidations lives in `subscriber.ts`.
 */
export type ServerEvent = {
  kind: string;
  source_module: string;
  ts: string;
  ticket_id: string | null;
  // Domain modules add extra fields per kind; we read them dynamically.
  [extra: string]: unknown;
};
