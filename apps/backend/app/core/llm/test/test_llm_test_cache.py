"""Unit tests for `LLMTestCache` — key derivation, JSON round-trip, miss behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.outputs import Generation

from app.core.llm import LLMTestCache


def _make_cache(tmp_path: Path, *, allow_real_calls: bool = True) -> LLMTestCache:
    """Build a cache that writes into `tmp_path` regardless of PYTEST_CURRENT_TEST."""
    return LLMTestCache(allow_real_calls=allow_real_calls, get_caller_dir=lambda: tmp_path)


_LLM_STRING = (
    json.dumps(
        {
            "kwargs": {
                "model": "anthropic:claude-haiku-4-5",
                "temperature": 0.1,
                "max_tokens": 256,
                "api_key": "sk-should-be-ignored",
                "base_url": "https://gateway.example",
            }
        }
    )
    + "---stop=['<END>']"
)


_PROMPT = json.dumps(
    [
        {"kwargs": {"type": "system", "content": "You are a classifier."}},
        {"kwargs": {"type": "human", "content": "Verdict for {{ subject }}?"}},
    ]
)


def test_key_is_stable_across_environment_fields(tmp_path: Path) -> None:
    """Changing only ignored fields (API key, base URL, UUIDs) doesn't change the key."""
    cache = _make_cache(tmp_path)
    k1 = cache._get_cache_key(_PROMPT, _LLM_STRING)
    llm_string_with_different_envs = (
        json.dumps(
            {
                "kwargs": {
                    "model": "anthropic:claude-haiku-4-5",
                    "temperature": 0.1,
                    "max_tokens": 256,
                    "api_key": "sk-totally-different",
                    "base_url": "https://other.example",
                }
            }
        )
        + "---stop=['<END>']"
    )
    k2 = cache._get_cache_key(_PROMPT, llm_string_with_different_envs)
    assert k1 == k2


def test_key_changes_when_model_changes(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path)
    k1 = cache._get_cache_key(_PROMPT, _LLM_STRING)
    other_model = _LLM_STRING.replace("claude-haiku-4-5", "claude-opus-4-5")
    k2 = cache._get_cache_key(_PROMPT, other_model)
    assert k1 != k2


def test_key_changes_when_temperature_changes(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path)
    k1 = cache._get_cache_key(_PROMPT, _LLM_STRING)
    other_temp = _LLM_STRING.replace('"temperature": 0.1', '"temperature": 0.9')
    k2 = cache._get_cache_key(_PROMPT, other_temp)
    assert k1 != k2


def test_key_changes_when_prompt_content_changes(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path)
    k1 = cache._get_cache_key(_PROMPT, _LLM_STRING)
    other_prompt = _PROMPT.replace("Verdict", "Decision")
    k2 = cache._get_cache_key(other_prompt, _LLM_STRING)
    assert k1 != k2


def test_html_entities_in_content_are_unescaped_before_hashing(tmp_path: Path) -> None:
    """Mustache `{{var}}` gets HTML-escaped by some renderers — should not change key."""
    cache = _make_cache(tmp_path)
    plain = json.dumps([{"kwargs": {"type": "system", "content": "Use {{var}} here."}}])
    escaped = json.dumps([{"kwargs": {"type": "system", "content": "Use &#123;&#123;var&#125;&#125; here."}}])
    assert cache._get_cache_key(plain, _LLM_STRING) == cache._get_cache_key(escaped, _LLM_STRING)


def test_update_then_lookup_round_trips(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path)
    cache.update(_PROMPT, _LLM_STRING, [Generation(text="cached response")])

    result = cache.lookup(_PROMPT, _LLM_STRING)

    assert result is not None
    assert len(result) == 1
    assert result[0].text == "cached response"
    assert cache.get_cache_stats()["hits"] == 1


def test_update_writes_file_in_caller_dir(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path)
    cache.update(_PROMPT, _LLM_STRING, [Generation(text="hello")])

    written = tmp_path / ".langchain_cache.json"
    assert written.exists()
    payload = json.loads(written.read_text())
    assert len(payload) == 1


def test_cache_miss_raises_when_allow_real_calls_false(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path, allow_real_calls=False)

    with pytest.raises(RuntimeError, match="CACHE MISS ERROR"):
        cache.lookup(_PROMPT, _LLM_STRING)


def test_cache_miss_returns_none_when_allow_real_calls_true(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path, allow_real_calls=True)

    assert cache.lookup(_PROMPT, _LLM_STRING) is None
    assert cache.get_cache_stats()["misses"] == 1


def test_clear_removes_cache_file(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path)
    cache.update(_PROMPT, _LLM_STRING, [Generation(text="x")])
    assert (tmp_path / ".langchain_cache.json").exists()

    cache.clear()

    assert not (tmp_path / ".langchain_cache.json").exists()


def test_get_cache_stats_returns_copy(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path)
    cache.update(_PROMPT, _LLM_STRING, [Generation(text="x")])
    cache.lookup(_PROMPT, _LLM_STRING)

    snapshot = cache.get_cache_stats()
    snapshot["hits"] = 999  # mutating the snapshot must not affect the cache

    assert cache.get_cache_stats()["hits"] == 1


def test_reset_cache_stats_clears_counters(tmp_path: Path) -> None:
    cache = _make_cache(tmp_path)
    cache.update(_PROMPT, _LLM_STRING, [Generation(text="x")])
    cache.lookup(_PROMPT, _LLM_STRING)

    cache.reset_cache_stats()

    stats = cache.get_cache_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["miss_details"] == []
