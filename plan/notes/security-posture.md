# yaaos security posture — unfinished agenda

> **Shipped security posture lives in [`docs/system-security.md`](../../docs/system-security.md).** This note retains only the unfinished agenda: future hardening, broader runtime coverage, defense-in-depth options that haven't shipped yet. Items move from here into `docs/system-security.md` as they ship.

## Federated identity — broader runtime coverage

Today: AWS STS SigV4 only. The Go agent + control-plane verifier ([`core/agent_gateway/sts_verifier.py`](../../apps/backend/app/core/agent_gateway/sts_verifier.py)) implement the Vault AWS auth pattern. `orgs.registered_iam_arn` is the trust anchor.

Future:

- **Generic OIDC** for GCP, Azure, EKS, plain Kubernetes, Fly.io, GitHub Actions. Agent fetches a short-lived OIDC token from its runtime's metadata service; control plane verifies the JWT against the issuer's JWKS and matches `iss` + `aud` + `sub` claim pattern to the customer's registered federation config. OIDC is a strict generalization of sigv4 — same security model, broader runtime coverage. AWS-ECS-without-EKS stays on sigv4 (no native OIDC endpoint).
- **Bare VM / dev laptop fallback.** No native IdP — agent exchanges a one-time bootstrap token (single-use, ≤15min TTL, workspace-scoped) for a locally-generated ed25519 keypair on first run. Private key never leaves the host; subsequent calls sign short-lived JWTs verifiable against the stored public key. POC-grade; not recommended for production.

## Defense-in-depth — network

- **Per-workspace source-IP allowlist enforced at the Cloudflare edge** before any compute spins up. Opt-in only; ephemeral-IP runtimes (GH Actions, dev laptops) can't usefully populate it. Useful for static-IP customer deployments.

## Multi-cloud workspace runtime

Today: AWS ECS is the documented + shipped customer runtime (`apps/agent/docs/README.md` deployment guide, sigv4 identity verifier).

Future:

- **GKE / AKS / EKS / Fly Machines / Cloud Run** runtime support. Same container, same wire protocol; per-platform glue is the metadata-service shape (for OIDC) and the autoscaling primitive.
- **Customer-native autoscaling docs** for each runtime: HPA on Kubernetes, Cloud Run autoscaling on GCP, Fly Machines autoscaling. Same metrics-emit shape; per-platform glue is the verb (CloudWatch `PutMetricData` on AWS today).

## Enterprise option — cross-account spin-up

Today: agents are long-running workers the customer deploys and sizes. Control plane never calls customer-side cloud APIs.

Future:

- **Cross-account `ecs:RunTask`** (or per-platform equivalent — `gcloud run jobs execute`, `fly machines run`) for per-job spin-up + scale-to-zero. Requires yaaos to assume a role in the customer's cloud account; explicitly opt-in. Default model stays as-is.

## Source-code-leakage guardrails — extensions

Today (shipped in `docs/system-security.md`): workspace process has no control-plane credentials; findings cross only via supervisor's audited event channel; `_safe_tool_input` strips Edit/Write/MultiEdit content from ActivityEvents.

Future:

- **Finding-body excerpt audit.** Code excerpts in finding bodies are the explicit exception to "source stays in VPC." A surface-aware audit (truncation, fingerprinting, customer-visible diff of what crosses) would tighten the boundary.
- **Per-process sandbox hardening.** Today: path validation in Go + `os.RLimit`. Future: landlock (Linux 5.13+) for filesystem confinement; seccomp filters; per-workspace UID; network namespaces. Each is independently valuable; M05 deferred all per [requirements.md § M05 does not ship](../milestones/M05-workspace-agent/requirements.md).
