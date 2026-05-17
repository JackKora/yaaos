"""File-colocated cache for LangChain LLM responses.

Replicates the dscout-core-py / astro pattern (`.langchain_cache.json`
colocated with the test file that triggered the lookup, committed to git).
Each test module gets its own JSON file; cache keys hash a whitelist of
semantic prompt + model-config fields so environment churn doesn't
invalidate entries.

To populate or update a cache file:
1. `pytest --allow-llm-calls` — real LLM calls are made and the responses
   appended to the colocated `.langchain_cache.json`.
2. Commit the updated file.

Default runs (no flag) require the cache to be populated already — cache
miss raises a loud `RuntimeError` telling you to re-run with the flag.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from langchain_core._api import LangChainBetaWarning
from langchain_core.caches import BaseCache
from langchain_core.load import dumps
from langchain_core.load.load import Reviver
from langchain_core.outputs import Generation

# Class paths whose load via `Reviver` is permitted. Includes the app
# namespace so domain-specific subclasses (Pydantic models, custom message
# types) round-trip cleanly.
ALLOWED_NAMESPACES: tuple[str, ...] = ("app", "langchain", "langchain_core")


def _get_caller_dir() -> Path:
    """Return the directory of the test file that triggered the lookup.

    Reads `PYTEST_CURRENT_TEST` (set by pytest) and resolves the parent of
    the file path. Raises if not inside a pytest run.
    """
    if "PYTEST_CURRENT_TEST" in os.environ:
        test_path = os.environ["PYTEST_CURRENT_TEST"].split("::")[0]
        return Path(test_path).parent
    raise RuntimeError(
        "Cannot determine test file location for cache. LLMTestCache can only be used during pytest runs."
    )


def _get_worker_id() -> str | None:
    """pytest-xdist worker id when running in parallel; `None` otherwise."""
    return os.environ.get("PYTEST_XDIST_WORKER")


class LLMTestCache(BaseCache):
    """LangChain `BaseCache` that stores generations in JSON files next to tests.

    One `.langchain_cache.json` (or `.langchain_cache_gw0.json` per xdist
    worker) per test directory. Files are pretty-printed and committed.
    """

    def __init__(
        self,
        filename: str = ".langchain_cache.json",
        allow_real_calls: bool = True,
        get_caller_dir: Callable[[], Path] | None = None,
    ) -> None:
        self.filename = filename
        self.allow_real_calls = allow_real_calls
        self.get_caller_dir = get_caller_dir or _get_caller_dir
        # Track whether we're using the default `PYTEST_CURRENT_TEST`-based
        # resolver — only those callers need xdist worker isolation. Tests
        # that inject `get_caller_dir` (e.g. a `tmp_path` fixture) already
        # have isolation built in.
        self._use_default_caller_dir = get_caller_dir is None
        self._cache_instances: dict[str, dict[str, Any]] = {}
        self.cache_stats: dict[str, Any] = {
            "hits": 0,
            "misses": 0,
            "miss_details": [],
        }

    def _get_cache_for_caller(self) -> tuple[Path, dict[str, Any]]:
        cache_dir = self.get_caller_dir()

        worker_id = _get_worker_id() if self._use_default_caller_dir else None
        if worker_id:
            base_name = Path(self.filename).stem
            extension = Path(self.filename).suffix
            cache_filename = f"{base_name}_{worker_id}{extension}"
            cache_path = cache_dir / cache_filename
        else:
            cache_path = cache_dir / self.filename

        cache_key = str(cache_path)

        if cache_key not in self._cache_instances:
            cache_data: dict[str, Any] = {}

            # When running under xdist, also read the committed main file so
            # workers benefit from existing entries before writing their own.
            if worker_id:
                main_cache_path = cache_dir / self.filename
                if main_cache_path.exists():
                    try:
                        with open(main_cache_path, encoding="utf-8") as f:
                            cache_data = json.load(f)
                    except (json.JSONDecodeError, OSError) as e:
                        print(f"Warning: Could not load main cache from {main_cache_path}: {e}")

            if cache_path.exists():
                try:
                    with open(cache_path, encoding="utf-8") as f:
                        worker_cache_data = json.load(f)
                        cache_data.update(worker_cache_data)
                except (json.JSONDecodeError, OSError) as e:
                    print(f"Warning: Could not load cache from {cache_path}: {e}")

            self._cache_instances[cache_key] = cache_data

        return cache_path, self._cache_instances[cache_key]

    def _save_cache(self, cache_path: Path, cache_data: dict[str, Any]) -> None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, sort_keys=True, ensure_ascii=False)
        except OSError as e:
            print(f"Warning: Could not save cache to {cache_path}: {e}")

    def _get_cache_key(self, prompt: str, llm_string: str) -> str:
        """Hash a whitelist of semantic prompt + LLM-config fields.

        Whitelisting keeps the key stable across environment / SDK churn
        (UUIDs, timeouts, API base URLs, etc. are excluded).
        """
        prompt_data = self._extract_prompt_semantic_fields(prompt)
        llm_data = self._extract_llm_semantic_fields(llm_string)
        combined = json.dumps({"prompt": prompt_data, "llm": llm_data}, sort_keys=True)
        return hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()

    def _extract_prompt_semantic_fields(self, prompt: str) -> list[dict[str, Any]]:
        try:
            messages = json.loads(prompt)
            semantic_messages: list[dict[str, Any]] = []
            for msg in messages:
                semantic_msg: dict[str, Any] = {}
                kwargs = msg.get("kwargs", {})
                if "type" in kwargs:
                    semantic_msg["type"] = kwargs["type"]
                if "content" in kwargs:
                    content = kwargs["content"]
                    # Mustache-style templating ({{var}}) gets HTML-escaped by
                    # some renderers but not others; unescape so the key is
                    # stable across environments.
                    if isinstance(content, str):
                        content = html.unescape(content)
                    semantic_msg["content"] = content
                if "tool_calls" in kwargs:
                    semantic_msg["tool_calls"] = kwargs["tool_calls"]
                if "name" in kwargs:
                    semantic_msg["name"] = kwargs["name"]
                semantic_messages.append(semantic_msg)
            return semantic_messages
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Warning: Could not parse prompt, using raw content: {e}")
            return [{"content": prompt}]

    def _extract_llm_semantic_fields(self, llm_string: str) -> dict[str, Any]:
        try:
            parts = llm_string.split("---", 1)
            if len(parts) != 2:
                return {"raw": llm_string}
            llm_config = json.loads(parts[0])
            params_str = parts[1]
            kwargs = llm_config.get("kwargs", {})

            semantic_field_names = [
                "model",
                "model_name",
                "temperature",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
                "max_tokens",
                "n",
            ]
            semantic_fields: dict[str, Any] = {
                field: kwargs[field] for field in semantic_field_names if field in kwargs
            }
            # Stop sequences and other model-side params come through `params_str`.
            semantic_fields["params"] = params_str
            return semantic_fields
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Warning: Could not parse llm_string, using raw: {e}")
            return {"raw": llm_string}

    def _get_test_file_info(self) -> str:
        if "PYTEST_CURRENT_TEST" in os.environ:
            test_info = os.environ["PYTEST_CURRENT_TEST"]
            test_path = test_info.split("::")[0]
            try:
                return str(Path(test_path).relative_to(Path.cwd()))
            except ValueError:
                return test_path
        return "unknown_test"

    def lookup(self, prompt: str, llm_string: str) -> Sequence[Generation] | None:
        try:
            cache_path, cache_data = self._get_cache_for_caller()
            key = self._get_cache_key(prompt, llm_string)
        except Exception as e:
            print(f"ERROR in lookup: {e}")
            return None

        if key in cache_data:
            try:
                # Reviver with `allowed_class_paths=None` disables langchain's
                # built-in class-path allowlist (langchain-core 1.3.3+) — that
                # allowlist only covers langchain's own classes, not domain
                # subclasses. Namespace gating via `valid_namespaces` is the
                # fallback and is enough for a trusted test cache.
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=LangChainBetaWarning)
                    reviver = Reviver("all", valid_namespaces=list(ALLOWED_NAMESPACES))
                    reviver.allowed_class_paths = None

                    def _load(obj: Any) -> Any:
                        if isinstance(obj, dict):
                            loaded = {k: _load(v) for k, v in obj.items()}
                            return reviver(loaded)
                        if isinstance(obj, list):
                            return [_load(o) for o in obj]
                        return obj

                    cached_result = _load(json.loads(cache_data[key]))
                self.cache_stats["hits"] += 1
                return cached_result
            except (TypeError, ValueError) as e:
                print(f"Warning: Could not deserialize cached generation for key {key}: {e}")
                cache_data.pop(key, None)
                self._save_cache(cache_path, cache_data)

        self.cache_stats["misses"] += 1
        test_file = self._get_test_file_info()
        self.cache_stats["miss_details"].append(
            {"test_file": test_file, "cache_file": str(cache_path), "key": key[:8]}
        )

        if not self.allow_real_calls:
            raise RuntimeError(
                f"CACHE MISS ERROR: No cached response found for key {key[:8]} in {cache_path}.\n"
                f"Test file: {test_file}\n"
                f"LLM calls are disabled in test mode. To allow real LLM calls, run with: pytest --allow-llm-calls\n"
                f"To populate the cache, run the test with --allow-llm-calls first."
            )
        return None

    def update(self, prompt: str, llm_string: str, return_val: Sequence[Generation]) -> None:
        try:
            cache_path, cache_data = self._get_cache_for_caller()
            key = self._get_cache_key(prompt, llm_string)
        except Exception as e:
            print(f"ERROR in update: {e}")
            return
        try:
            cache_data[key] = dumps(return_val)
            self._save_cache(cache_path, cache_data)
        except (TypeError, ValueError, OSError) as e:
            print(f"Warning: Could not cache generation for key {key}: {e}")

    def clear(self) -> None:
        cache_path, _ = self._get_cache_for_caller()
        try:
            if cache_path.exists():
                os.remove(cache_path)
            cache_key = str(cache_path)
            if cache_key in self._cache_instances:
                del self._cache_instances[cache_key]
        except OSError as e:
            print(f"Warning: Could not clear cache file {cache_path}: {e}")

    async def alookup(self, prompt: str, llm_string: str) -> Sequence[Generation] | None:
        return self.lookup(prompt, llm_string)

    async def aupdate(self, prompt: str, llm_string: str, return_val: Sequence[Generation]) -> None:
        return self.update(prompt, llm_string, return_val)

    async def aclear(self) -> None:
        return self.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        return dict(self.cache_stats)

    def reset_cache_stats(self) -> None:
        self.cache_stats = {"hits": 0, "misses": 0, "miss_details": []}
