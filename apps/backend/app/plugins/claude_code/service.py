"""Claude Code CLI wrapper. Implements core/coding_agent.CodingAgentPlugin.

POC behavior: when env var `YAAOF_CODING_AGENT_STUB=1` is set, the plugin returns
deterministic canned `FindingList`-shaped responses based on the agent name
extracted from the prompt header. This keeps tests offline + CI-friendly without
needing a pre-populated cache file. The real CLI invocation path is kept intact
for production use.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from app.core.coding_agent import (
    AgentInvocationResult,
    AgentInvocationStatus,
    HealthStatus,
    ValidationResult,
    register_coding_agent_plugin,
)
from app.core.config import get_settings
from app.core.database import session as db_session
from app.core.workspace import Workspace
from app.plugins.claude_code.models import ClaudeCodeSettingsRow

log = structlog.get_logger("claude_code")


def _is_stub_mode() -> bool:
    return os.environ.get("YAAOF_CODING_AGENT_STUB", "").lower() in {"1", "true", "yes"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _agent_name_from_prompt(prompt: str) -> str:
    """Extract `architecture` / `security` / `style` from the `# Agent: <name>` header.
    Falls back to 'unknown' if unparseable.
    """
    for line in prompt.splitlines()[:5]:
        line = line.strip()
        if line.startswith("# Agent:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


# Canned stub findings per agent — deterministic but realistic-looking.
_STUB_FINDINGS_BY_AGENT: dict[str, list[dict[str, Any]]] = {
    "architecture": [
        {
            "file": None,
            "line_start": None,
            "line_end": None,
            "severity": "suggestion",
            "title": "Consider extracting shared logic",
            "body": "The introduced helper could live in a shared module so other callers benefit.",
            "rationale": "Reducing duplication makes future changes cheaper.",
            "snippet": None,
            "applied_lesson_ids": [],
        }
    ],
    "security": [
        {
            "file": None,
            "line_start": None,
            "line_end": None,
            "severity": "info",
            "title": "No security-sensitive code paths detected",
            "body": "Diff appears low-risk: no auth, secrets, or input-validation changes.",
            "rationale": None,
            "snippet": None,
            "applied_lesson_ids": [],
        }
    ],
    "style": [
        {
            "file": None,
            "line_start": None,
            "line_end": None,
            "severity": "nit",
            "title": "Comment phrasing could be tightened",
            "body": "A few comments restate what the code already says — could remove them.",
            "rationale": "Comments cost reader attention without adding signal.",
            "snippet": None,
            "applied_lesson_ids": [],
        }
    ],
}


def _stub_result(prompt: str, response_model: type[BaseModel]) -> AgentInvocationResult[Any]:
    """Return a deterministic AgentInvocationResult matching the requested response_model."""
    agent_name = _agent_name_from_prompt(prompt)
    findings = _STUB_FINDINGS_BY_AGENT.get(agent_name, [])
    # The reviewer's FindingList has shape { findings: [...] }; ReplyResponse has { body: str }.
    payload: dict[str, Any]
    fields = response_model.model_fields
    if "findings" in fields:
        payload = {"findings": findings}
    elif "body" in fields:
        payload = {"body": f"[{agent_name}] Thanks for the reply — taking another look."}
    else:
        payload = {}
    raw = json.dumps(payload)
    try:
        parsed = response_model.model_validate(payload)
    except ValidationError as e:
        return AgentInvocationResult(
            status=AgentInvocationStatus.PARSE_FAILURE,
            raw_output=raw,
            raw_stderr="",
            error_message=f"stub response did not match {response_model.__name__}: {e}",
            latency_ms=1,
        )
    return AgentInvocationResult(
        status=AgentInvocationStatus.SUCCESS,
        parsed=parsed,
        raw_output=raw,
        raw_stderr="",
        tokens_in=1000,
        tokens_out=200,
        cost_usd=Decimal("0.0050"),
        latency_ms=10,
    )


class ClaudeCodePlugin:
    plugin_id = "claude_code"

    def __init__(self) -> None:
        # API key + CLI path are read lazily so plugin construction at import time
        # doesn't require a live DB.
        pass

    async def _load_settings_for_invocation(self) -> tuple[str | None, str | None, int]:
        """Returns (decrypted_api_key, cli_path, timeout_seconds)."""
        async with db_session() as s:
            row = (await s.execute(select(ClaudeCodeSettingsRow).limit(1))).scalar_one_or_none()
        if row is None:
            return None, None, 600
        api_key: str | None = None
        if row.encrypted_anthropic_api_key:
            try:
                fernet = Fernet(get_settings().yaaof_encryption_key.encode())
                api_key = fernet.decrypt(row.encrypted_anthropic_api_key).decode()
            except InvalidToken:
                log.warning("claude_code.api_key_decrypt_failed")
        return api_key, row.cli_path, row.default_timeout_seconds

    async def invoke(
        self,
        workspace: Workspace,
        prompt: str,
        agent_config: dict[str, Any],
        response_model: type[BaseModel],
    ) -> AgentInvocationResult[Any]:
        if _is_stub_mode():
            return _stub_result(prompt, response_model)

        api_key, cli_path_setting, default_timeout = await self._load_settings_for_invocation()
        if not api_key:
            return AgentInvocationResult(
                status=AgentInvocationStatus.AGENT_ERROR,
                error_message="ANTHROPIC_API_KEY not set in claude_code_settings",
                latency_ms=0,
            )
        cli_path = cli_path_setting or shutil.which("claude")
        if not cli_path:
            return AgentInvocationResult(
                status=AgentInvocationStatus.AGENT_ERROR,
                error_message="claude binary not found on PATH or in claude_code_settings.cli_path",
                latency_ms=0,
            )

        # Schema appendix
        full_prompt = (
            f"{prompt}\n\n## Output Format (STRICT)\n\n"
            "Respond with EXACTLY a JSON object matching this schema. No markdown fences. "
            "No commentary. No preamble. Your response must start with `{` and end with `}`.\n\n"
            f"{json.dumps(response_model.model_json_schema(), indent=2)}\n"
        )

        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = api_key
        timeout = agent_config.get("timeout_seconds") or default_timeout
        argv = [
            cli_path,
            "--print",
            "--output-format=json",
            "--permission-mode=bypassPermissions",
            "--allowed-tools=Read,Glob,Grep,LS,NotebookRead,TodoWrite,WebFetch,WebSearch",
        ]
        if agent_config.get("model"):
            argv += [f"--model={agent_config['model']}"]
        if agent_config.get("max_turns"):
            argv += [f"--max-turns={agent_config['max_turns']}"]

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=workspace.working_dir,
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as e:
            return AgentInvocationResult(
                status=AgentInvocationStatus.AGENT_ERROR,
                error_message=f"could not spawn claude: {e}",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode("utf-8")), timeout=timeout
            )
        except TimeoutError:
            try:
                proc.send_signal(signal.SIGTERM)
                await asyncio.sleep(2)
                if proc.returncode is None:
                    proc.kill()
            except ProcessLookupError:
                pass
            return AgentInvocationResult(
                status=AgentInvocationStatus.TIMEOUT,
                error_message=f"claude did not return within {timeout}s",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        latency_ms = int((time.monotonic() - start) * 1000)
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            return AgentInvocationResult(
                status=AgentInvocationStatus.AGENT_ERROR,
                raw_output=stdout,
                raw_stderr=stderr,
                latency_ms=latency_ms,
                error_message=f"claude exited {proc.returncode}: {stderr.splitlines()[0] if stderr else ''}",
            )

        try:
            envelope = json.loads(stdout)
            agent_text = envelope.get("result", "")
            usage = envelope.get("usage", {})
            tokens_in = usage.get("input_tokens")
            tokens_out = usage.get("output_tokens")
            cost = envelope.get("total_cost_usd")
            cost_usd = Decimal(str(cost)) if cost is not None else None
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            return AgentInvocationResult(
                status=AgentInvocationStatus.AGENT_ERROR,
                raw_output=stdout,
                raw_stderr=stderr,
                latency_ms=latency_ms,
                error_message=f"could not parse claude wrapper output: {e}",
            )

        try:
            parsed_dict = json.loads(agent_text)
            parsed = response_model.model_validate(parsed_dict)
        except (json.JSONDecodeError, ValidationError) as e:
            return AgentInvocationResult(
                status=AgentInvocationStatus.PARSE_FAILURE,
                raw_output=agent_text,
                raw_stderr=stderr,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                error_message=f"agent response didn't match {response_model.__name__}: {e}",
            )

        return AgentInvocationResult(
            status=AgentInvocationStatus.SUCCESS,
            parsed=parsed,
            raw_output=agent_text,
            raw_stderr=stderr,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )

    async def validate_config(self, agent_config: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        if "timeout_seconds" in agent_config:
            v = agent_config["timeout_seconds"]
            if not isinstance(v, int) or v <= 0:
                errors.append("timeout_seconds must be a positive int")
        if "max_turns" in agent_config:
            v = agent_config["max_turns"]
            if not isinstance(v, int) or v <= 0:
                errors.append("max_turns must be a positive int")
        if "model" in agent_config:
            v = agent_config["model"]
            if not isinstance(v, str) or not v:
                errors.append("model must be a non-empty string")
        unknown = set(agent_config) - {"timeout_seconds", "max_turns", "model"}
        errors.extend(f"unknown config key: {k}" for k in unknown)
        return ValidationResult(valid=not errors, errors=errors)

    async def health_check(self) -> HealthStatus:
        if _is_stub_mode():
            return HealthStatus(healthy=True, message="stub mode", checked_at=_utcnow())
        api_key, cli_path_setting, _ = await self._load_settings_for_invocation()
        if not api_key:
            return HealthStatus(healthy=False, message="anthropic api key not set", checked_at=_utcnow())
        cli_path = cli_path_setting or shutil.which("claude")
        if not cli_path:
            return HealthStatus(healthy=False, message="claude binary not found", checked_at=_utcnow())
        return HealthStatus(healthy=True, message="ok", checked_at=_utcnow())


_plugin = ClaudeCodePlugin()


async def _onboarding_anthropic_key_set(org_id: UUID) -> bool:
    """Settings contributor — returns True iff a key is present."""
    async with db_session() as s:
        row = (
            await s.execute(select(ClaudeCodeSettingsRow).where(ClaudeCodeSettingsRow.org_id == org_id))
        ).scalar_one_or_none()
    return row is not None and row.encrypted_anthropic_api_key is not None


async def _set_anthropic_key(org_id: UUID, raw_key: str) -> None:
    """Encrypt + upsert the Anthropic key on `claude_code_settings`."""
    from uuid import uuid4  # noqa: PLC0415

    fernet = Fernet(get_settings().yaaof_encryption_key.encode())
    enc = fernet.encrypt(raw_key.encode())
    async with db_session() as s:
        row = (
            await s.execute(select(ClaudeCodeSettingsRow).where(ClaudeCodeSettingsRow.org_id == org_id))
        ).scalar_one_or_none()
        if row is None:
            row = ClaudeCodeSettingsRow(
                id=uuid4(),
                org_id=org_id,
                encrypted_anthropic_api_key=enc,
                default_timeout_seconds=600,
            )
            s.add(row)
        else:
            row.encrypted_anthropic_api_key = enc
        await s.commit()


def bootstrap() -> None:
    from app.domain.settings import (  # noqa: PLC0415
        register_credential_setter,
        register_onboarding_contributor,
    )

    register_coding_agent_plugin(_plugin)
    register_onboarding_contributor("anthropic_key_set", _onboarding_anthropic_key_set)
    register_credential_setter("anthropic_api_key", _set_anthropic_key)


def get_plugin() -> ClaudeCodePlugin:
    return _plugin
