"""core/webserver — FastAPI app factory, RouteSpec registry, SPA serving."""

from app.core.webserver.app_factory import create_app, mount_specs
from app.core.webserver.registry import RouteSpec, register_routes

__all__ = ["RouteSpec", "create_app", "mount_specs", "register_routes"]
