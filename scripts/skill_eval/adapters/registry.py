"""Task and judge harness adapter registries."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, TypeVar

from ..core import EvalError, EvaluationCondition
from ..harness import Harnesses, JudgeHarness, TaskHarness


@dataclass
class HarnessBuildContext:
    """Adapter-neutral settings and per-evaluation shared construction state."""

    conditions: tuple[EvaluationCondition, ...]
    task_model: str | None
    judge_model: str | None
    timeout_seconds: int
    sandbox: str
    peer_skills: tuple[Path, ...]
    deadline_seconds: int | None
    binary_overrides: Mapping[str, str]
    _shared: dict[str, object] = field(default_factory=dict, init=False, repr=False)

    def shared(self, key: str, factory: Callable[[], object]) -> object:
        """Return one adapter-owned dependency for this evaluation build."""

        if key not in self._shared:
            self._shared[key] = factory()
        return self._shared[key]


HarnessT = TypeVar("HarnessT", TaskHarness, JudgeHarness)
HarnessBuilder = Callable[[HarnessBuildContext], HarnessT]


class HarnessAdapterRegistry(Generic[HarnessT]):
    """Resolve one harness role by a stable, user-facing adapter identifier."""

    def __init__(self, role: str) -> None:
        self.role = role
        self._builders: dict[str, HarnessBuilder[HarnessT]] = {}

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._builders))

    def register(self, adapter_id: str, builder: HarnessBuilder[HarnessT]) -> None:
        normalized = adapter_id.strip()
        if not normalized or normalized != adapter_id:
            raise ValueError(f"{self.role} adapter ids must be non-empty and trimmed")
        if normalized in self._builders:
            raise ValueError(f"{self.role} adapter {normalized!r} is already registered")
        self._builders[normalized] = builder

    def resolve(self, adapter_id: str) -> HarnessBuilder[HarnessT]:
        try:
            return self._builders[adapter_id]
        except KeyError as exc:
            available = ", ".join(self.ids) or "none"
            raise EvalError(
                f"Unknown {self.role} adapter {adapter_id!r}. Available {self.role} "
                f"adapters: {available}"
            ) from exc


TASK_ADAPTER_REGISTRY = HarnessAdapterRegistry[TaskHarness]("task")
JUDGE_ADAPTER_REGISTRY = HarnessAdapterRegistry[JudgeHarness]("judge")
_BUILTINS_REGISTERED = False
_BUILTINS_LOCK = threading.Lock()


def _ensure_builtin_adapters() -> None:
    global _BUILTINS_REGISTERED
    with _BUILTINS_LOCK:
        if _BUILTINS_REGISTERED:
            return
        from .codex import register_codex_adapters

        register_codex_adapters(TASK_ADAPTER_REGISTRY, JUDGE_ADAPTER_REGISTRY)
        _BUILTINS_REGISTERED = True


def validate_adapter_selection(task_adapter: str, judge_adapter: str) -> None:
    """Resolve both roles without constructing a harness or touching credentials."""

    _ensure_builtin_adapters()
    TASK_ADAPTER_REGISTRY.resolve(task_adapter)
    JUDGE_ADAPTER_REGISTRY.resolve(judge_adapter)


def registered_harness_factory(
    *,
    task_adapter: str,
    judge_adapter: str,
    conditions: tuple[EvaluationCondition, ...],
    codex_binary: str,
    model: str | None,
    judge_model: str | None,
    timeout_seconds: int,
    sandbox: str,
    peer_skills: tuple[Path, ...],
    deadline_seconds: int | None,
) -> Harnesses:
    """Build independently selected task and judge adapters from the registries."""

    _ensure_builtin_adapters()
    task_builder = TASK_ADAPTER_REGISTRY.resolve(task_adapter)
    judge_builder = JUDGE_ADAPTER_REGISTRY.resolve(judge_adapter)
    context = HarnessBuildContext(
        conditions=conditions,
        task_model=model,
        judge_model=judge_model,
        timeout_seconds=timeout_seconds,
        sandbox=sandbox,
        peer_skills=peer_skills,
        deadline_seconds=deadline_seconds,
        binary_overrides={"codex": codex_binary},
    )
    return Harnesses(
        task=task_builder(context),
        judge=judge_builder(context),
    )
