---
name: yaaos-review-security
description: Deep security audit of code changes or a codebase area. Checks OWASP top 10, auth/authz patterns, data exposure, injection vectors, dependency CVEs, and secrets. Goes deeper than a code review.
disable-model-invocation: true
---

# Security Audit

Perform a focused security audit. This goes deeper than the security checks in a code review — it's a dedicated pass looking for vulnerabilities, misconfigurations, and data exposure risks.

## Getting Started

Determine scope:
- If `$ARGUMENTS` contains a PR number → audit that PR's changes
- If `$ARGUMENTS` contains file paths → audit those files and their callers
- If `$ARGUMENTS` names a feature or area → discover and audit all related code
- If empty → ask the user what to audit

## Step 1 — Map the Attack Surface

Spawn parallel agents:
- **codebase-locator**: Find all files related to the audit scope
- **codebase-analyzer**: Trace data flow from entry points (user input, API requests, webhooks, queue messages) through processing to storage and output

Identify:
- All entry points where external data enters the system
- All exits where data leaves (responses, logs, emails, third-party APIs)
- All trust boundaries (auth checks, permission gates, service boundaries)
- All data stores touched (databases, caches, file systems, queues)

## Step 2 — OWASP Top 10 Check

Systematically check for each category:

### A01: Broken Access Control
- Are auth/authz checks present on every endpoint that needs them?
- Can a user access or modify another user's resources? (IDOR)
- Are permission checks at the data layer, not just the UI?
- Can API endpoints be called directly, bypassing UI-level guards?

### A02: Cryptographic Failures
- Is sensitive data encrypted at rest and in transit?
- Are there hardcoded secrets, API keys, or credentials?
- Is password hashing using a strong algorithm (bcrypt, argon2)?
- Are TLS configurations current?

### A03: Injection
- SQL injection: Are queries parameterized? Any string concatenation in queries?
- XSS: Is user input sanitized before rendering? Are CSP headers set?
- Command injection: Is user input ever passed to shell commands?
- Template injection: Are template engines used safely?

### A04: Insecure Design
- Are there rate limits on sensitive operations (login, password reset, API)?
- Are business logic flows validated server-side (not just client)?
- Are there anti-automation measures where needed?

### A05: Security Misconfiguration
- Are debug modes, verbose errors, or stack traces exposed in production?
- Are default credentials or configurations in use?
- Are CORS policies appropriate (not wildcard)?
- Are security headers set (CSP, X-Frame-Options, HSTS)?

### A06: Vulnerable Components
- Check dependency files (mix.lock, package-lock.json, requirements.txt, etc.)
- Spawn **docs-researcher** to check for known CVEs in dependencies
- Are dependencies pinned to specific versions?
- Are there outdated packages with known vulnerabilities?

### A07: Authentication Failures
- Are sessions managed securely? (httpOnly, secure, SameSite cookies)
- Is session fixation possible?
- Are password policies enforced?
- Is MFA available for sensitive operations?

### A08: Data Integrity Failures
- Are deserialized objects validated?
- Are CI/CD pipelines secured against tampering?
- Are software updates verified (signatures, checksums)?

### A09: Logging & Monitoring Failures
- Are security events logged (failed logins, permission denials, input validation failures)?
- Is sensitive data excluded from logs (passwords, tokens, PII)?
- Are logs tamper-resistant?

### A10: SSRF
- Can user input influence server-side HTTP requests?
- Are internal service URLs accessible via user-controlled parameters?
- Are allowlists in place for external requests?

## Step 3 — Data Exposure Analysis

Trace sensitive data (PII, credentials, tokens, financial data) through the system:
- Where does it enter?
- Where is it stored?
- Where is it logged? (should it be?)
- Where does it exit? (API responses, error messages, emails)
- Who can access it? (roles, permissions)
- Is it ever exposed in URLs, query parameters, or client-side code?

## Step 4 — Secrets Scan

Check for hardcoded secrets:
- API keys, tokens, passwords in source code
- `.env` files committed to version control
- Credentials in configuration files, docker-compose, CI configs
- Private keys or certificates in the repo

## Step 5 — Report

```markdown
## Security Audit: [Scope]
Date: [ISO timestamp]
Auditor: Claude

### Critical Findings (immediate action required)
#### 1. [Vulnerability type]: [Title]
**Location:** `file:line`
**Risk:** [What an attacker could do]
**Evidence:** [Specific code or configuration that's vulnerable]
**Fix:** [Concrete remediation with code]

### High Findings (fix before merge/release)
...

### Medium Findings (fix soon)
...

### Low Findings (improve when convenient)
...

### Dependency Vulnerabilities
| Package | Version | CVE | Severity | Fix Version |
|---------|---------|-----|----------|-------------|

### Positive Security Patterns
- [Things done well — reinforces good practices]

### Recommendations
1. [Prioritized next steps]
```

## Step 6 — Adversarial Challenge

Before presenting, spawn the **adversarial-debate** agent to challenge your security findings. False positives erode trust in security audits — this step is critical.

Format all findings (critical through low) as structured claims and pass them to the agent along with:
- The file paths and code references for each finding
- The data flow traces from Step 1
- The dependency versions from lockfiles

The agent will:
- Verify every file:line reference against current code
- Challenge exploitability — "you say this is injectable, but is the input actually user-controlled? Trace it."
- Steel-man the existing security posture — "you flagged missing rate limiting, but is there a WAF or reverse proxy handling this?"
- Calibrate severity — "you rated this critical, but the blast radius is a single user's session, not system-wide"
- Verify that suggested fixes don't introduce new vulnerabilities
- Check dependency CVEs against the ACTUAL versions in lockfiles (not just the package name)

Apply the agent's verdicts:
- **KEEP**: finding is exploitable and correctly severity-rated
- **DOWNGRADE**: adjust severity to match actual risk
- **REVISE**: narrow the claim to what's actually demonstrated
- **DROP**: remove false positives — note them in a "Considered and Dismissed" section

After applying verdicts, confirm:
- [ ] Every surviving finding includes a concrete fix
- [ ] Severity classifications reflect actual exploitability, not theoretical worst-case

## Guidelines

- Focus on EXPLOITABLE vulnerabilities, not theoretical risks
- Every finding needs a concrete fix — not just "consider improving"
- Severity must reflect actual risk, not worst-case imagination
- Acknowledge what's done WELL — good security patterns should be reinforced
- Check the ACTUAL code, not what you assume it does
