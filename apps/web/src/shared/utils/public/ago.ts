/** Relative-time formatter. Returns "12s ago" / "3m ago" / "2h ago" / "5d ago" / "—". */
export function ago(ts: string | null | undefined): string {
  if (!ts) return "—";
  const then = new Date(ts).getTime();
  if (Number.isNaN(then)) return "—";
  const sec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

/** Wall-clock time-of-day in the browser's local timezone — `HH:MM:SS`. Use
 *  this anywhere the UI shows a specific moment (audit-log rows, etc.). The
 *  backend emits ISO-8601 UTC; `Intl` converts it to the user's local TZ.
 *
 *  Anti-pattern: never call `.toISOString()` for display — that returns UTC.
 */
export function formatTime(ts: string | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString(undefined, { hour12: false });
}

/** Full local-timezone date + time-of-day, e.g. "2026-05-16, 18:28:00". */
export function formatDateTime(ts: string | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, { hour12: false });
}
