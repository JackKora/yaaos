# fake-github

> Peer Python service that fakes every GitHub endpoint yaaos's `plugins/github` calls. Test stack only.

## Purpose

Tests exercise the github plugin's real code paths — JWT signing, HMAC verification, REST round-trips — without hitting `api.github.com`. Minimal FastAPI service implementing every endpoint yaaos calls plus a `/__test/*` control surface for seeding and dispatching HMAC-signed webhooks. `GITHUB_API_BASE_URL` points yaaos here; plugin code is unchanged between prod and test.

Not a yaaos backend module — absent from `tach.toml`, the module map, layering rules. Peer service.

## GitHub-compatible endpoints

| Method + path | Behavior |
|---|---|
| `GET /app` | `{id, slug: "yaaos-test"}`. Health checks. |
| `POST /app/installations/{id}/access_tokens` | `{token: "ghs_fake_<id>_x", expires_at: <+1h>}`. |
| `GET /repos/{owner}/{repo}` | `{full_name, default_branch: "main"}`. |
| `GET /repos/{owner}/{repo}/pulls/{number}` | Seeded PR JSON. With `Accept: application/vnd.github.v3.diff`, returns raw diff. |
| `GET .../pulls/{number}/files` | Seeded file list. |
| `GET .../pulls?state=open` | All seeded PRs for the repo. |
| `GET .../pulls/{number}/comments` | Inline comments yaaos has posted (in-memory). |
| `GET .../issues/{number}/comments` | Top-level comments yaaos has posted. |
| `POST .../pulls/{number}/reviews` | Records the review. Returns `{id, html_url, comment_external_ids}`. |
| `POST .../pulls/{number}/comments/{parent}/replies` | Records an inline reply. |
| `POST .../issues/{number}/comments` | Records an issue-comment fallback. |
| `GET /installation/repositories` | Seeded repo list. Drives the catch-up poller and the Settings repo list. |
| `GET .../compare/{before}...{after}` | `{status: <seeded or "ahead">}`. Force-push spec seeds `"diverged"`. |

Bearer-protected endpoints accept any bearer — the fake validates only that one is present.

## Test-control endpoints

| Method + path | Behavior |
|---|---|
| `POST /__test/reset` | Clears in-memory state, re-seeds defaults (acme/web#1, acme/api#1, default repo list). Called by every spec in `beforeEach`. |
| `POST /__test/seed_pr` | `{owner, repo, number, pr}`. Auto-called by the e2e `dispatchWebhook` helper for `pull_request` events. |
| `POST /__test/seed_diff` | `{owner, repo, number, diff, files}`. |
| `POST /__test/seed_compare_status` | `{base_to_head, status}`. Force-push spec uses this to inject `"diverged"`. |
| `POST /__test/dispatch_webhook` | `{event, payload, target_url, delivery_id?}`. HMAC-signs with the shared test webhook secret, POSTs to `target_url` with `X-Hub-Signature-256` + `X-GitHub-Event` + `X-GitHub-Delivery`. How specs simulate "a PR opened on GitHub." |
| `GET /__test/posted_reviews` | What yaaos has POSTed. Used for outbound-call assertions. |
| `GET /__test/posted_comments` | Same shape, for comments. |

## Auth

Two shared secrets in `app/test_secrets.py` (committed; obviously fake):
- `APP_ID` — App's numeric id.
- `WEBHOOK_SECRET` — yaaos's HMAC verification on inbound; signing on `/__test/dispatch_webhook` outbound. Override with `GITHUB_WEBHOOK_SECRET` (set in `docker-compose.test.yml`).

App private key is not real RSA. yaaos's `_build_app_jwt` detects the missing `BEGIN ... PRIVATE KEY` header and emits `jwt-fake-<app_id>`, which fake-github accepts. Production uses real RS256 via `pyjwt`.

## In-memory state

`app/state.py` singleton `FakeGitHubState`:
- `seeded_prs: dict[str, dict]` — `"owner/repo#number"` → PR JSON.
- `seeded_diffs: dict[str, str]` — same key → raw diff.
- `seeded_files: dict[str, list[dict]]` — same key → file summaries.
- `installation_repositories: list[dict]`.
- `compare_status: dict[str, str]` — `"before...after"` → status.
- `posted_reviews`, `posted_comments` — what yaaos has POSTed.
- `_next_review_id`, `_next_comment_id` — auto-increment counters.

`POST /__test/reset` clears everything and re-seeds defaults from `app/seeds.py`: PRs `acme/web#1`, `acme/api#1`; repo entries `acme/web`, `acme/api`.

## Running locally

`cd apps/fake-github && uv sync && uv run uvicorn app.main:app --port 8081`. Usually run via `docker-compose.test.yml` alongside the backend.

## Tech

- Python 3.13 + FastAPI.
- Own `pyproject.toml`; uv workspace member.
- Single-file `Dockerfile`. ~280 LOC. No DB; state in-memory.

## What fake-github does NOT do

- Doesn't verify the App JWT signature — any bearer prefix accepted.
- Doesn't model rate limits or HTTP errors beyond a few cases (e.g., 404 on missing PRs).
- Doesn't validate HMAC on inbound `/__test/*` — trust-by-deployment (reachable only inside the test stack network).
- Doesn't simulate webhook retries — `/__test/dispatch_webhook` is one-shot.
