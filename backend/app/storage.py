from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.schemas import (
    AdaptationPlan,
    AppliedAdaptation,
    DataPolicy,
    Revision,
    StoryState,
    TargetScript,
)


def _now() -> datetime:
    return datetime.now(UTC)


class MarketProfile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    market: str = Field(default="", max_length=200)
    audience: str = Field(default="", max_length=200)
    format: str = Field(default="", max_length=200)
    genre: str = Field(default="", max_length=200)
    source_language: str = Field(default="zh-CN", min_length=1, max_length=100)
    target_language: str = Field(default="English", min_length=1, max_length=100)
    target_locale: str = Field(default="en-US", max_length=100)
    style_guide: str = Field(default="", max_length=10_000)
    terminology_map: dict[str, str] = Field(default_factory=dict)

    @field_validator("terminology_map")
    @classmethod
    def _bounded_terminology_map(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 500:
            raise ValueError("terminology_map cannot contain more than 500 entries")
        if any(not key or len(key) > 200 or not term or len(term) > 500 for key, term in value.items()):
            raise ValueError("terminology_map keys and values must be non-empty and bounded")
        return value


class ProjectMeta(BaseModel):
    id: str
    name: str = ""
    created_at: datetime = Field(default_factory=_now)
    script_text: str
    market: MarketProfile = Field(default_factory=MarketProfile)
    owner_id: str = "local"
    data_policy: DataPolicy = Field(default_factory=DataPolicy)


class ProjectStore:
    def __init__(self, projects_dir: Path) -> None:
        self.projects_dir = projects_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def _dir(self, project_id: str) -> Path:
        if not project_id or not project_id.isalnum() or len(project_id) < 4:
            raise KeyError(f"invalid project id: {project_id!r}")
        path = self.projects_dir / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _peek_dir(self, project_id: str) -> Path:
        if not project_id or not project_id.isalnum() or len(project_id) < 4:
            raise KeyError(f"invalid project id: {project_id!r}")
        return self.projects_dir / project_id

    def _history_dir(self, project_id: str) -> Path:
        path = self._dir(project_id) / "history"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _write_json(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _read_json(path: Path):
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return None

    def create_project(
        self,
        name: str,
        script_text: str,
        market: MarketProfile,
        *,
        owner_id: str = "local",
        data_policy: DataPolicy | None = None,
    ) -> ProjectMeta:
        project_id = uuid.uuid4().hex
        meta = ProjectMeta(
            id=project_id,
            name=name,
            script_text=script_text,
            market=market,
            owner_id=owner_id,
            data_policy=data_policy or DataPolicy(),
        )
        self._write_json(self._dir(project_id) / "project.json", meta.model_dump(mode="json"))
        return meta

    def list_projects(self) -> list[ProjectMeta]:
        metas: list[ProjectMeta] = []
        for project_dir in sorted(self.projects_dir.iterdir()):
            raw = self._read_json(project_dir / "project.json")
            if raw is not None:
                metas.append(ProjectMeta.model_validate(raw))
        return metas

    def load_meta(self, project_id: str) -> ProjectMeta | None:
        raw = self._read_json(self._peek_dir(project_id) / "project.json")
        return ProjectMeta.model_validate(raw) if raw else None

    def delete_project(self, project_id: str) -> bool:
        project_dir = self._peek_dir(project_id)
        if not project_dir.exists():
            return False
        shutil.rmtree(project_dir)
        return True

    def load_state(self, project_id: str) -> StoryState | None:
        raw = self._read_json(self._peek_dir(project_id) / "state.json")
        if raw is None:
            return None
        try:
            state = StoryState.model_validate(raw)
        except ValidationError:
            return None
        if not state.scenes and not state.characters:
            return None
        if state.version == 0:
            raw_revisions = self._read_json(
                self._peek_dir(project_id) / "revisions.json"
            ) or []
            state.version = max(
                (
                    int(revision.get("state_version") or revision.get("revision_id") or 0)
                    for revision in raw_revisions
                    if isinstance(revision, dict)
                ),
                default=0,
            )
        return state

    def list_revisions(self, project_id: str) -> list[Revision]:
        raw = self._read_json(self._peek_dir(project_id) / "revisions.json")
        revisions = [Revision.model_validate(r) for r in (raw or [])]
        state = self.load_state(project_id)
        if state is None:
            return []
        return [
            revision
            for revision in revisions
            if (revision.state_version or revision.revision_id) <= state.version
        ]

    def save_state(
        self,
        project_id: str,
        state: StoryState,
        kind: str,
        description: str = "",
        changed_scene_ids: list[str] | None = None,
        applied_option: dict | None = None,
        applied: AppliedAdaptation | None = None,
    ) -> Revision:
        current_state = self.load_state(project_id)
        current_version = current_state.version if current_state is not None else 0
        next_version = current_version + 1
        state.version = next_version
        revision_id = next_version
        current_revisions = self.list_revisions(project_id)
        revision = Revision(
            revision_id=revision_id,
            state_version=next_version,
            kind=kind,
            description=description,
            changed_scene_ids=changed_scene_ids or [],
            applied_option=applied_option,
        )

        self._write_json(
            self._history_dir(project_id) / f"rev{revision_id:03d}.json",
            state.model_dump(mode="json"),
        )
        self._write_json(
            self._dir(project_id) / "revisions.json",
            [r.model_dump(mode="json") for r in [*current_revisions, revision]],
        )
        if applied is not None:
            applied.state_version = next_version
            existing = self.load_applied(project_id)
            existing.append(applied)
            self._write_json(
                self._dir(project_id) / "adaptations.json",
                [item.model_dump(mode="json") for item in existing],
            )
        # state.json is the commit marker and must be replaced last.
        self._write_json(self._dir(project_id) / "state.json", state.model_dump(mode="json"))
        return revision

    def save_plan(self, project_id: str, plan: AdaptationPlan) -> None:
        plans = [
            p
            for p in self.load_plans(project_id)
            if p.culture_mechanism_id != plan.culture_mechanism_id
        ]
        plans.append(plan)
        self._write_json(
            self._dir(project_id) / "plans.json",
            [p.model_dump(mode="json") for p in plans],
        )

    def load_plans(self, project_id: str) -> list[AdaptationPlan]:
        raw = self._read_json(self._peek_dir(project_id) / "plans.json")
        return [AdaptationPlan.model_validate(p) for p in (raw or [])]

    def load_plan(self, project_id: str, mechanism_id: str) -> AdaptationPlan | None:
        return next(
            (p for p in self.load_plans(project_id) if p.culture_mechanism_id == mechanism_id),
            None,
        )

    def append_applied(self, project_id: str, applied: AppliedAdaptation) -> None:
        state = self.load_state(project_id)
        if state is not None and applied.state_version == 0:
            applied.state_version = state.version
        existing = self.load_applied(project_id)
        existing.append(applied)
        self._write_json(
            self._dir(project_id) / "adaptations.json",
            [a.model_dump(mode="json") for a in existing],
        )

    def load_applied(self, project_id: str) -> list[AppliedAdaptation]:
        raw = self._read_json(self._peek_dir(project_id) / "adaptations.json")
        applied = [AppliedAdaptation.model_validate(a) for a in (raw or [])]
        state = self.load_state(project_id)
        if state is None:
            return []
        return [
            item
            for item in applied
            if item.state_version == 0 or item.state_version <= state.version
        ]

    def save_target_script(self, project_id: str, target_script: TargetScript) -> None:
        self._write_json(
            self._dir(project_id) / "target_script.json",
            target_script.model_dump(mode="json"),
        )

    def load_target_script(self, project_id: str) -> TargetScript | None:
        raw = self._read_json(self._peek_dir(project_id) / "target_script.json")
        if raw is None:
            return None
        try:
            target_script = TargetScript.model_validate(raw)
        except ValidationError:
            return None
        state = self.load_state(project_id)
        if state is None or target_script.source_state_version != state.version:
            return None
        return target_script
