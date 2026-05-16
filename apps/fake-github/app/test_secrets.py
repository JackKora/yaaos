"""Obviously-fake test secrets shared between yaaof + fake-github."""

# 40-byte hex HMAC secret — committed; TEST-FAKE-NOT-FOR-PROD.
WEBHOOK_SECRET = "TEST-FAKE-NOT-FOR-PROD-aaaaaaaaaaaaaaaa"

# A placeholder PEM string. fake-github does NOT actually verify RSA signatures;
# it accepts any Bearer token prefixed `jwt-fake-`.
APP_PRIVATE_KEY_PEM = "-----BEGIN PRIVATE KEY-----\nTEST-FAKE-NOT-FOR-PROD\n-----END PRIVATE KEY-----\n"

APP_ID = "12345"
