from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator

from app.schemas.privacy import DataPolicy


@dataclass(frozen=True, slots=True)
class ProjectDataContext:
    project_id: str = ""
    policy: DataPolicy = field(default_factory=DataPolicy)


_CURRENT_DATA_CONTEXT: ContextVar[ProjectDataContext] = ContextVar(
    "storybridge_data_context", default=ProjectDataContext()
)


def current_data_context() -> ProjectDataContext:
    return _CURRENT_DATA_CONTEXT.get()


@contextmanager
def project_data_context(
    project_id: str, policy: DataPolicy
) -> Iterator[ProjectDataContext]:
    context = ProjectDataContext(project_id=project_id, policy=policy)
    token = _CURRENT_DATA_CONTEXT.set(context)
    try:
        yield context
    finally:
        _CURRENT_DATA_CONTEXT.reset(token)
