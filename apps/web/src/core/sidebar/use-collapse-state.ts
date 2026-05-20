import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "yaaos.sidebar.collapse";

interface CollapseState {
  [groupId: string]: boolean; // true = collapsed
}

function read(): CollapseState {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed ? parsed : {};
  } catch {
    return {};
  }
}

function write(state: CollapseState): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Quota exceeded or storage disabled — non-fatal; just lose persistence.
  }
}

/**
 * Per-group collapse state, keyed by group `id`, persisted to localStorage.
 * Default for an unseen group is `false` (expanded).
 */
export function useCollapseState() {
  const [state, setState] = useState<CollapseState>(() => read());

  // Cross-tab sync — keeps two open windows from drifting when the user
  // collapses a group in one of them.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setState(read());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const isCollapsed = useCallback((id: string) => Boolean(state[id]), [state]);
  const toggle = useCallback((id: string) => {
    setState((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      write(next);
      return next;
    });
  }, []);

  return { isCollapsed, toggle };
}
