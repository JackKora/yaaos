"""Rate limit on identity exchange."""

from __future__ import annotations

import pytest

from app.core.agent_gateway.rate_limit import (
    PER_IP_LIMIT,
    RateLimitedError,
    check_identity_exchange,
)

pytestmark = pytest.mark.usefixtures("redis_or_skip")


async def test_per_ip_limit_kicks_in() -> None:
    ip = f"10.0.0.{__import__('random').randint(1, 250)}"
    for _ in range(PER_IP_LIMIT):
        await check_identity_exchange(source_ip=ip)
    with pytest.raises(RateLimitedError) as exc_info:
        await check_identity_exchange(source_ip=ip)
    assert exc_info.value.axis == "ip"


async def test_none_source_ip_skips_check() -> None:
    # No-op when source_ip is None (test harness / proxy stripping).
    await check_identity_exchange(source_ip=None)
