from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.schemas import AdaptationPlan, AppliedAdaptation, Revision, StoryState


def _now() -> datetime:
    return datetime.now(UTC)


class MarketProfile(BaseModel):
    market: str = ""
    audience: str = ""
    format: str = ""
    genre: str = ""


class ProjectMeta(BaseModel):
    id: str
    name: str = ""
    created_at: datetime = Field(default_factory=_now)
    script_text: str
    market: MarketProfile = Field(default_factory=MarketProfile)


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
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json(self, path: Path):
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return None

    def create_project(self, name: str, script_text: str, market: MarketProfile) -> ProjectMeta:
        project_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        meta = ProjectMeta(id=project_id, name=name, script_text=script_text, market=market)
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
        return state

    def list_revisions(self, project_id: str) -> list[Revision]:
        raw = self._read_json(self._peek_dir(project_id) / "revisions.json")
        return [Revision.model_validate(r) for r in (raw or [])]

    def save_state(
        self,
        project_id: str,
        state: StoryState,
        kind: str,
        description: str = "",
        changed_scene_ids: list[str] | None = None,
        applied_option: dict | None = None,
    ) -> Revision:
        revision_id = len(self.list_revisions(project_id)) + 1
        self._write_json(self._dir(project_id) / "state.json", state.model_dump(mode="json"))
        self._write_json(
            self._history_dir(project_id) / f"rev{revision_id:03d}.json",
            state.model_dump(mode="json"),
        )
        revision = Revision(
            revision_id=revision_id,
            kind=kind,
            description=description,
            changed_scene_ids=changed_scene_ids or [],
            applied_option=applied_option,
        )
        self._write_json(
            self._dir(project_id) / "revisions.json",
            [r.model_dump(mode="json") for r in [*self.list_revisions(project_id), revision]],
        )
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
        existing = self.load_applied(project_id)
        existing.append(applied)
        self._write_json(
            self._dir(project_id) / "adaptations.json",
            [a.model_dump(mode="json") for a in existing],
        )

    def load_applied(self, project_id: str) -> list[AppliedAdaptation]:
        raw = self._read_json(self._peek_dir(project_id) / "adaptations.json")
        return [AppliedAdaptation.model_validate(a) for a in (raw or [])]
