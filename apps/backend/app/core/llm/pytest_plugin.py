"""Pytest plugin for `core/llm` consumers.

Auto-loaded via `[project.entry-points."pytest11"]` in
`apps/backend/pyproject.toml`. Adds `--allow-llm-calls`, installs an autouse
session-scoped `LLMTestCache`, and prints a hit/miss summary at session end.
"""

from __future__ import annotations

import pytest
from langchain_core.globals import set_llm_cache

from app.core.llm.llm_test_cache import LLMTestCache


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--allow-llm-calls",
        action="store_true",
        default=False,
        help="Allow real LLM API calls during tests (default: cache-only mode).",
    )


@pytest.fixture(scope="session", autouse=True)
def setup_llm_cache(request: pytest.FixtureRequest):  # type: ignore[no-untyped-def]
    """Install the file-colocated LLM cache for the whole session.

    Each test file gets its own `.langchain_cache.json` next to it. With
    `--allow-llm-calls`, real calls are made and the cache is updated.
    Without it, a cache miss raises a loud `RuntimeError`.
    """
    allow_llm_calls = request.config.getoption("--allow-llm-calls")
    cache = LLMTestCache(allow_real_calls=allow_llm_calls)
    set_llm_cache(cache)
    pytest.llm_cache = cache  # type: ignore[attr-defined]
    yield


@pytest.fixture
def allow_llm_calls(request: pytest.FixtureRequest) -> None:
    """Skip the test unless `--allow-llm-calls` is passed.

    Tests that depend on the cache being populated (or on real LLM calls)
    declare this fixture; default runs skip them.
    """
    if not request.config.getoption("--allow-llm-calls", default=False):
        pytest.skip("Requires --allow-llm-calls (LLM cache must be populated first)")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Print cache hit/miss summary at the end of the session."""
    cache = getattr(pytest, "llm_cache", None)
    if cache is None:
        return
    stats = cache.get_cache_stats()
    total_requests = stats["hits"] + stats["misses"]
    if total_requests == 0:
        return

    print("\n" + "=" * 60)
    print("LLM CACHE STATISTICS")
    print("=" * 60)
    print(f"Total LLM requests: {total_requests}")
    print(f"Cache hits: {stats['hits']} ({stats['hits'] / total_requests * 100:.1f}%)")
    print(f"Cache misses: {stats['misses']} ({stats['misses'] / total_requests * 100:.1f}%)")
    if stats["miss_details"]:
        print("\nCache misses by test:")
        for miss in stats["miss_details"]:
            print(f"  • Test: {miss['test_file']}")
            print(f"    Cache file: {miss['cache_file']}")
            print(f"    Key: {miss['key']}...")
            print()
    print("=" * 60)
