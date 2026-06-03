import type { Notification, NotificationsPopover } from "@core/api";
import { http, HttpResponse } from "msw";

/** Default fixture — all four date-bucket entries. Override per-test via server.use(). */
export const NOTIFICATIONS_FIXTURE: Notification[] = [
  {
    id: "n1",
    user_id: "u1",
    org_id: "o1",
    type: "hitl_waiting",
    ticket_id: "t1",
    title: "Today event",
    body: "body 1",
    read_at: null,
    created_at: new Date().toISOString(),
  },
];

export const POPOVER_FIXTURE: NotificationsPopover = {
  items: NOTIFICATIONS_FIXTURE,
  unread_count: 1,
};

export const notificationHandlers = [
  http.get("/api/notifications", () => {
    return HttpResponse.json(NOTIFICATIONS_FIXTURE);
  }),

  http.post("/api/notifications/:id/read", ({ params }) => {
    const found = NOTIFICATIONS_FIXTURE.find((n) => n.id === params.id);
    if (!found) {
      return HttpResponse.json({ error: "not found" }, { status: 404 });
    }
    return HttpResponse.json({ ...found, read_at: new Date().toISOString() });
  }),

  http.post("/api/notifications/mark-read", () => {
    return HttpResponse.json({ marked: NOTIFICATIONS_FIXTURE.length });
  }),

  http.get("/api/notifications/popover", () => {
    return HttpResponse.json(POPOVER_FIXTURE);
  }),
];
