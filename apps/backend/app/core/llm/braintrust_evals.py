"""Thin Braintrust `Eval(...)` wrapper used by domain modules.

Owner modules call `create_eval(...)` from their `<module>/eval/*.eval.py`
files. core/llm owns the wrapper because every prompt-using module wants
the same `(experiment_name, project, task, scorers, dataset)` shape; the
actual fixtures + scorers stay in the owner module.

Per `plan/notes/full-pr-flow.md` §14.8, this stays intentionally small —
no Braintrust-prompt-as-parameter machinery (prompts are file-based in
`<module>/llm/prompts/*.prompt.md`, not registered in Braintrust).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from braintrust.framework import EvalScorer, EvalTask


def create_eval(
    *,
    experiment_name: str,
    module_name: str,
    task: EvalTask,
    scores: Sequence[EvalScorer],
    dataset_name: str,
    max_concurrency: int | None = None,
) -> Any:
    """Construct a `braintrust.Eval` bound to `module_name` as the project.

    Args:
        experiment_name: Shown in the Braintrust UI for this run.
        module_name: Braintrust project (use the owning domain module name).
        task: `(input, hooks) -> output` function.
        scores: List of scorer functions (`autoevals` or hand-written).
        dataset_name: Name of the dataset already registered in Braintrust.
        max_concurrency: Cap on parallel task executions. `None` = unlimited.
            Set to 1 for tasks that call `asyncio.run()` to avoid event-loop
            deadlocks.
    """
    # Local import so the dep stays optional for callers that don't run evals.
    from braintrust import Eval, init_dataset  # noqa: PLC0415

    return Eval(
        name=module_name,
        experiment_name=experiment_name,
        data=init_dataset(project=module_name, name=dataset_name),
        task=task,
        scores=list(scores),
        max_concurrency=max_concurrency,
    )
