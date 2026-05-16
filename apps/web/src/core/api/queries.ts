import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type AuditEntry,
  type HealthResponse,
  type Lesson,
  type OnboardingStatus,
  type Repo,
  type ReviewJob,
  type ReviewerAgent,
  type Ticket,
  apiClient,
  apiFetch,
} from "./client";

export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/health");
      if (error) throw new Error("health check failed");
      if (!data) throw new Error("no data");
      return data;
    },
    refetchInterval: 5_000,
  });
}

export function useOnboarding() {
  return useQuery<OnboardingStatus>({
    queryKey: ["onboarding"],
    queryFn: () => apiFetch<OnboardingStatus>("/api/settings/onboarding"),
    refetchInterval: 5_000,
  });
}

export function useRepos() {
  return useQuery<Repo[]>({
    queryKey: ["repos"],
    queryFn: () => apiFetch<Repo[]>("/api/repos"),
  });
}

export function useAddRepo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (external_id: string) =>
      apiFetch<Repo>("/api/repos", {
        method: "POST",
        body: JSON.stringify({ external_id, plugin_id: "github" }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repos"] }),
  });
}

export function useRemoveRepo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (repo_id: string) =>
      apiFetch<{ status: string }>(`/api/repos/${repo_id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repos"] }),
  });
}

export function useTickets() {
  return useQuery<Ticket[]>({
    queryKey: ["tickets"],
    queryFn: () => apiFetch<Ticket[]>("/api/tickets"),
    refetchInterval: 3_000,
  });
}

export function useTicket(ticket_id: string) {
  return useQuery<Ticket>({
    queryKey: ["tickets", ticket_id],
    queryFn: () => apiFetch<Ticket>(`/api/tickets/${ticket_id}`),
    enabled: !!ticket_id,
  });
}

export function useTicketAudit(ticket_id: string) {
  return useQuery<AuditEntry[]>({
    queryKey: ["tickets", ticket_id, "audit"],
    queryFn: () => apiFetch<AuditEntry[]>(`/api/tickets/${ticket_id}/audit`),
    enabled: !!ticket_id,
    refetchInterval: 3_000,
  });
}

export function useReviewJobsForTicket(ticket_id: string) {
  return useQuery<ReviewJob[]>({
    queryKey: ["reviewer", "jobs", ticket_id],
    queryFn: () => apiFetch<ReviewJob[]>(`/api/reviewer/jobs/by-ticket/${ticket_id}`),
    enabled: !!ticket_id,
    refetchInterval: 3_000,
  });
}

export function useRereviewMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ticket_id: string) =>
      apiFetch<{ scheduled_count: number }>("/api/reviewer/rereview", {
        method: "POST",
        body: JSON.stringify({ ticket_id }),
      }),
    onSuccess: (_, ticket_id) => {
      qc.invalidateQueries({ queryKey: ["reviewer", "jobs", ticket_id] });
      qc.invalidateQueries({ queryKey: ["tickets", ticket_id, "audit"] });
    },
  });
}

export function useLessons(repo_id?: string) {
  return useQuery<Lesson[]>({
    queryKey: ["memory", repo_id ?? "all"],
    queryFn: () => apiFetch<Lesson[]>(`/api/memory${repo_id ? `?repo_id=${repo_id}` : ""}`),
  });
}

export function useCreateLesson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (l: {
      repo_id: string;
      title: string;
      body: string;
      source_pr_url?: string | null;
    }) =>
      apiFetch<Lesson>("/api/memory", {
        method: "POST",
        body: JSON.stringify(l),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memory"] }),
  });
}

export function useDeleteLesson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ status: string }>(`/api/memory/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memory"] }),
  });
}

export function useReviewerAgents() {
  return useQuery<ReviewerAgent[]>({
    queryKey: ["reviewer", "agents"],
    queryFn: () => apiFetch<ReviewerAgent[]>("/api/reviewer/agents"),
  });
}

export function useUpdateAgentPrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { name: string; prompt_text: string }) =>
      apiFetch<ReviewerAgent>(`/api/reviewer/agents/${args.name}/prompt`, {
        method: "PUT",
        body: JSON.stringify({ prompt_text: args.prompt_text }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviewer", "agents"] }),
  });
}

export function useResetAgentPrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch<ReviewerAgent>(`/api/reviewer/agents/${name}/reset_prompt`, {
        method: "POST",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviewer", "agents"] }),
  });
}

export function useMetricsSummary() {
  return useQuery<{
    review_jobs_by_status: Record<string, number>;
    total_reviews_posted: number;
    total_cost_usd: number;
    failure_count: number;
    failure_rate: number;
  }>({
    queryKey: ["reviewer", "metrics"],
    queryFn: () => apiFetch("/api/reviewer/metrics"),
    refetchInterval: 5_000,
  });
}

export function useSetAnthropicKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (api_key: string) =>
      apiFetch<{ status: string }>("/api/settings/anthropic_key", {
        method: "POST",
        body: JSON.stringify({ api_key }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["onboarding"] }),
  });
}
