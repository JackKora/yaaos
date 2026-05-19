"""plugins/oauth_test — test-only OAuth Provider stub.

The module asserts `settings.yaaos_env == "test"` at import time (see
`service.py`). Importing this module under any other env raises immediately —
a defensive guard so the stub can never accidentally accept real users.
"""

from app.plugins.oauth_test.service import (
    TestOAuthProvider,
    bootstrap,
    set_next_profile,
)

__all__ = ["TestOAuthProvider", "bootstrap", "set_next_profile"]

bootstrap()
