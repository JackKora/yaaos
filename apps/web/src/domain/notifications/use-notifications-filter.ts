import { useState } from "react";

export type ReadFilter = "all" | "unread" | "read";

/**
 * Manages the read-state filter chip for the notifications list.
 * Returns the current filter value and a setter — no JSX.
 */
export function useNotificationsFilter() {
  const [filter, setFilter] = useState<ReadFilter>("all");
  return { filter, setFilter } as const;
}
