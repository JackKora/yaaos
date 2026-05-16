"""Value objects + protocols shared across workspace consumers and plugins."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class WorkspaceStatus(StrEnum):
    CREATING = "creating"
    ACTIVE = "active"
    EXPIRED = "expired"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    DESTROY_FAILED = "destroy_failed"


class ResourceCaps(BaseModel):
    cpu_count: int = 2
    memory_mb: int = 2048
    wallclock_seconds: int = 600
    disk_mb: int = 10240


class NetworkPolicy(StrEnum):
    DENY_ALL = "deny_all"
    GITHUB_ONLY = "github_only"
    ALLOW_ALL = "allow_all"


class RepoRefForSpec(BaseModel):
    """Minimal repo identity in a workspace spec. Mirrors domain/vcs RepoRef."""

    plugin_id: str
    external_id: str


class WorkspaceSpec(BaseModel):
    repo: RepoRefForSpec
    sha: str
    branch_name: str | None = None
    resource_caps: ResourceCaps = Field(default_factory=ResourceCaps)
    network_policy: NetworkPolicy = NetworkPolicy.GITHUB_ONLY


class WorkspaceInfo(BaseModel):
    id: str
    provider_id: str
    sha: str
    working_dir: str
    status: WorkspaceStatus
    created_at: datetime
    activated_at: datetime | None
    expires_at: datetime
    destroyed_at: datetime | None
    age_seconds: float


class HealthStatus(BaseModel):
    healthy: bool
    message: str = ""
    checked_at: datetime


class Workspace(Protocol):
    """Returned to callers. Just an id + working_dir for M01."""

    id: str
    working_dir: str

    async def info(self) -> WorkspaceInfo: ...


class WorkspaceHandle(BaseModel):
    """What plugins return from provision()."""

    working_dir: str


class WorkspaceProvider(Protocol):
    plugin_id: str

    async def provision(self, spec: WorkspaceSpec) -> tuple[WorkspaceHandle, dict[str, Any]]: ...
    async def destroy(self, plugin_state: dict[str, Any]) -> None: ...
    async def health_check(self) -> HealthStatus: ...


class WorkspaceError(Exception):
    """Base for workspace errors."""


class WorkspaceProvisionError(WorkspaceError):
    """Raised by plugins when provision() fails."""


class WorkspaceNotFoundError(WorkspaceError, LookupError):
    """Raised by get_workspace() if the id is unknown."""


class WorkspaceExpiredError(WorkspaceError):
    """Raised when a caller acts on an already-expired workspace."""


class WorkspaceDestroyError(WorkspaceError):
    """Raised by plugins when destroy() fails."""
