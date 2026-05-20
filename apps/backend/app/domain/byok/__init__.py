"""domain/byok — HTTP wiring for `core/byok`.

Lives in `domain` rather than `core` because the BYOK endpoints depend on
`domain/auth` for the `require()` + `current_actor()` deps. `core/byok`
stays free of HTTP and free of domain imports; this module is a thin web
shim over it.
"""
