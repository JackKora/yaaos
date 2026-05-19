# Secret rotation

How to rotate every secret yaaos depends on. Each section is one paragraph + the env var name + the blast radius of a leak.

## `YAAOS_ENCRYPTION_KEY`

Fernet master key for plugin credentials (GitHub App PEM, webhook secret, Anthropic API key) and the fallback for TOTP + SAML SP private keys when their dedicated key isn't set. **Rotation requires re-encrypting every existing row** — there's no key-rotation table yet. Procedure: generate the new key, set both old + new on the backend, write a one-shot migration that decrypts with old and encrypts with new, swap the active key. Blast radius of a leak: every encrypted credential in the database becomes readable.

## `YAAOS_TOTP_MASTER_KEY`

Dedicated Fernet for TOTP secrets + per-org SAML SP private keys. Same rotation pattern as `YAAOS_ENCRYPTION_KEY`. When unset, the code falls back to `YAAOS_ENCRYPTION_KEY` — production deployments should set this separately so TOTP rotation can happen without touching plugin credentials. Blast radius: every TOTP secret + every SAML SP key.

## `YAAOS_OAUTH_STATE_SECRET`

`itsdangerous` HMAC secret for OAuth `state`, link-pending, TOTP-challenge, GitHub-install state, and stub SAML assertions. Short-lived signed tokens (10–15 min TTL); rotation invalidates every in-flight signed cookie/state — users mid-flow get a 400 and re-start. Safe to rotate at will. Blast radius: an attacker with the secret can forge any of those signed tokens until natural expiry.

## `YAAOS_INVITATION_TOKEN_SECRET`

`itsdangerous` HMAC secret for invitation tokens (7-day TTL). Rotation invalidates every pending invitation — re-invite everyone. Blast radius: an attacker can forge an `accept_invitation` for any seen email, but acceptance still requires a valid session cookie identifying the acceptor.

## `YAAOS_OAUTH_GITHUB_CLIENT_SECRET`

GitHub OAuth App secret. Rotate by generating a new client secret on GitHub, updating the env, restarting the backend. No DB migration. Blast radius: an attacker can complete the OAuth code-exchange step pretending to be yaaos — but the `state` signature still has to verify, so the impact is bounded to that one signed-state window.

## SMTP credentials

`SMTP_USERNAME` / `SMTP_PASSWORD`. Rotation is provider-specific (Mailgun / SES / etc.). Blast radius: attacker can send mail from yaaos's relay.
