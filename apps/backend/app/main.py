# ruff: noqa: I001
# I001 is disabled file-wide: the bootstrap order in this file is load-bearing
# (see patterns.md § Bootstrap composition order) and conflicts with isort's
# alphabetic grouping.
"""Entry point. Bootstrap order per `patterns.md` § Bootstrap composition order."""

# 1. Load environment.
from app.core import config  # noqa: F401

# 2. Configure core infrastructure.
from app.core import database, observability, primitives  # noqa: F401

observability.configure()

# 3. Events bus must exist before any domain module subscribes.
from app.core import events  # noqa: F401, E402

# 4. Webserver registry must exist before any domain module registers routes.
from app.core import webserver  # noqa: E402

# 5. Core modules whose plugins are domain-facing.
from app.core import audit_log, workspace, coding_agent  # noqa: F401, E402

# 6. Domain modules — order: types first (vcs), then leaf domain modules,
#    then domain modules that depend on others.
from app.domain import vcs  # noqa: F401, E402
from app.domain import repos  # noqa: F401, E402
from app.domain import pull_requests  # noqa: F401, E402
from app.domain import tickets  # noqa: F401, E402
from app.domain import memory  # noqa: F401, E402
from app.domain import reviewer  # noqa: F401, E402
from app.domain import intake  # noqa: F401, E402
from app.domain import settings  # noqa: F401, E402

# 7. Plugins.
from app.plugins import in_process_workspace, claude_code, github  # noqa: F401, E402

# 8. Build the FastAPI app.
app = webserver.create_app()
