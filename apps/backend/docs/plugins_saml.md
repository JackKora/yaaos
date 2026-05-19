# plugins/saml + plugins/saml_test

> SAML 2.0 SP — wraps `python3-saml` for production; `saml_test` is the test-only stub IdP.

## Purpose

Implements the SP side of the SAML AuthnRequest → Response → ACS round-trip for org-scoped SSO. The actual XML parsing + signature verification happens in `plugins/saml` via the OneLogin python3-saml library. `plugins/saml_test` issues `itsdangerous`-signed assertions standing in for real XML during automated tests — the goal is to exercise [domain/orgs](domain_orgs.md)'s SSO orchestration (config CRUD, ACS handler, session-satisfaction marking, JIT membership creation) without depending on `libxmlsec1` + a live IdP.

## Public interface

Both plugins push an assertion-verifier function into [`domain/orgs.sso`](domain_orgs.md)'s registry at import time. The orgs ACS handler runs all registered verifiers in order; the first non-None match wins.

- `plugins.saml.is_available()` — True when `python3-saml` imports cleanly. False in environments missing `libxmlsec1`/`xmlsec1`. The real-SAML verifier short-circuits to None when unavailable.
- `plugins.saml.parse_assertion(xml, settings_dict)` — verify + parse a SAML Response XML. Used internally by the registered verifier.
- `plugins.saml_test.sign_assertion(payload)` — encode a stub assertion (`{email, name_id, ...}`). Tests call this to drive ACS.
- `plugins.saml_test.verify_assertion(token)` — verify + return the payload.

## Module architecture

### Registry-based dispatch

`domain/orgs.sso.register_assertion_verifier(fn)` adds an assertion-verifier callable to a process-global list. `run_assertion_verifier(saml_response, idp_metadata_xml)` walks the list and returns the first non-None result. Inversion of control: orgs/sso doesn't import the plugins, the plugins push themselves in. Tach is happy (domain doesn't depend on plugins).

### Env-gating of `saml_test`

`plugins/saml_test/service.py` asserts `get_settings().yaaos_env == "test"` at import time. `main.py` only imports it under that env. Defense in depth so the stub can never accept assertions in prod.

### Real-SAML availability

`plugins/saml/service.is_available()` tries `import onelogin.saml2` and returns False on any failure (ImportError, OSError from missing libxmlsec1, etc.). The docker image installs `libxmlsec1-dev` + `xmlsec1` in Phase 0; bare-metal local-dev environments without the system libs degrade gracefully.

### Stub-assertion shape

The test stub's payload is `{"email": <verified-email>, "name_id": <stable-id>, ...}` — the same shape the real verifier returns. The orgs ACS handler reads `payload["email"]`, matches by verified email, optionally JIT-creates a membership, marks the session SSO-satisfied. Phase 12's E2E test uses the stub.

## Data owned

None. The SP per-org private key, IdP metadata XML, JIT toggle, and exempt-Owner pointer live in [`domain/orgs.sso_configs`](domain_orgs.md). The SP private key is Fernet-encrypted with `yaaos_totp_master_key` (or `yaaos_encryption_key` in non-prod).

## How it's tested

- `app/domain/orgs/test/test_sso.py` — config CRUD, ACS happy path (with the stub), JIT create, no-JIT reject, middleware enforces satisfaction, exempt-Owner bypass.
- Phase 12 Playwright spec drives login fail-without-SSO → SSO satisfies → JIT creates → middleware allows.
- The real `plugins/saml` parser is covered by integration tests against a real IdP image — outside the unit-test event loop.
