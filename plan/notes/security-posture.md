# yaaos security posture (no-private-routing model)

Hybrid SaaS architecture. Control plane hosted by yaaos.ai handles orchestration, UI, and persisted metadata. A customer-deployed workspace agent inside the customer's AWS VPC handles all code-touching work. Source code never enters yaaos infrastructure. Only structured findings, comment threads, and operational metadata cross the boundary. The architecture is designed so that no single credential leak — on either side — gives an attacker the ability to read customer source code or impersonate a customer in the control plane.

## Network

Public-internet HTTPS in both directions: workspace-to-control-plane (outbound from the customer's VPC) and webhook ingress from GitHub. No inbound port opened on the customer side. The security guarantee does not depend on network isolation; it depends on TLS for transport confidentiality plus AWS-signed identity proofs at the application layer, the same model used by every major B2B SaaS.

## Authentication

Anchored in AWS IAM. At startup the workspace fetches a cryptographically signed identity blob from AWS, which the control plane verifies against AWS's public keys and matches against the role ARN the customer registered for their organization. No long-lived shared secret is transmitted or stored.

Yaaos's marketplace GitHub App provides scoped, short-lived installation tokens for repository access. The App's private key is the only long-lived secret yaaos holds; it sits in KMS-managed storage with audit logging on every retrieval.

## Workspace lifecycle and scaling

Workspaces are long-running ECS workers that the customer deploys and sizes. The control plane never calls customer-side AWS APIs in the default model — it only adds work to a per-org queue. Agents poll over outbound HTTPS, pick up jobs, and post results back.

Per-review isolation happens inside the agent: each job runs in a fresh subdirectory that is created at job start and deleted at job end. The agent process is long-lived; the per-review sandbox is not. Source code, cloned repos, and intermediate artifacts never persist across jobs.

Scaling is driven by the customer's own ECS Service Auto Scaling, using a target-tracking policy on a CloudWatch metric. The metric value comes from the workspace agents themselves: on each poll, the control plane returns current queue depth, and the agent emits it via `cloudwatch:PutMetricData` under its existing IAM role. No new credential, no separate identity — the agent's role gets one additional permission scoped to a single CloudWatch namespace.

This pattern keeps yaaos out of the customer's AWS account entirely. Yaaos publishes a metrics endpoint; the customer's ECS, CloudWatch, and auto-scaling do the rest as standard managed services. A cross-account `ecs:RunTask` model exists as an enterprise option if a customer ever needs per-job spin-up with scale-to-zero, but it is not the default because it requires yaaos to assume a role inside the customer's AWS account.

- **No control-plane-initiated workspace spawning.** Workspaces are customer-deployed long-running workers; the control plane queues jobs, never launches infrastructure.
- **Per-review isolation via ephemeral subdirectories.** Each job's working tree is created and destroyed inside the agent process; nothing persists across jobs.
- **Scaling uses standard ECS target-tracking policies** on a CloudWatch metric — pure Terraform/CloudFormation configuration, no custom controller.
- **Queue-depth metric is emitted by agents under their existing IAM role**; the only added permission is `cloudwatch:PutMetricData` scoped to the `yaaos/workspace` namespace.
- **PutMetricData call volume is two orders of magnitude below AWS rate limits** at expected agent counts, and well within the CloudWatch free tier on cost.
- **Cross-account `ecs:RunTask` is an enterprise option, not the default.** The default model gives yaaos zero permissions in the customer's AWS account.

## LLM access — BYOK required

Bring-your-own-key is mandatory. The customer registers their own Anthropic/OpenAI account; the workspace agent uses that key directly when making model calls. All prompt content — including diff context the agent fetches via tool calls — flows from the workspace to the LLM provider over the customer's own commercial relationship. Yaaos never holds, proxies, or sees the customer's LLM credentials, and yaaos's infrastructure never sees prompt or response bodies. The only LLM-related data persisted in yaaos is the structured finding output the agent returns.

Code excerpts inside finding bodies are the explicit exception to "source stays in VPC" and are surfaced through the published finding schema so customers know exactly what crosses the boundary.

## Multi-tenancy and data at rest

Shared Postgres with strict `org_id` discipline at the repository layer, CI-enforced tenant-isolation tests, and an append-only audit log per organization. Data at rest is encrypted via managed database encryption with KMS-wrapped keys. Sensitive runtime values (the GitHub App private key, any customer-supplied credentials) use a separate KMS key from general application data, with access logged at the KMS layer.

## Distinguishing properties

- **No source code in yaaos.** Even a full compromise of the yaaos backend cannot exfiltrate customer source; the data model contains none.
- **BYOK is mandatory.** All AI processing runs through the customer's own LLM provider account; yaaos never holds, proxies, or sees those keys or the prompt content.
- **No long-lived per-customer secret in yaaos.** Per-org config is an ARN and a GitHub installation ID — both non-secret values.
- **Public workspace image is safe to leak.** Identity comes from AWS at runtime, not from anything baked into the image.
- **Customer revokes in two steps, no yaaos cooperation needed.** Detach the IAM role's trust policy and uninstall the GitHub App.
