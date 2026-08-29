from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from app.database import SQLiteDatabase
from app.schemas import (
    AdaptationPlan,
    AppliedAdaptation,
    DataPolicy,
    Revision,
    StoryState,
    TargetScript,
)
from app.storage import MarketProfile, ProjectMeta, ProjectStore


def _json_dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _now_text() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteProjectStore(ProjectStore):
    """SQLite-backed repository with the legacy file-store interface."""

    def __init__(self, database_path: Path, artifacts_dir: Path) -> None:
        self.projects_dir = artifacts_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.database = SQLiteDatabase(database_path)

    def create_project(
        self,
        name: str,
        script_text: str,
        market: MarketProfile,
        *,
        owner_id: str = "local",
        data_policy: DataPolicy | None = None,
    ) -> ProjectMeta:
        meta = ProjectMeta(
            id=uuid.uuid4().hex,
            name=name,
            script_text=script_text,
            market=market,
            owner_id=owner_id,
            data_policy=data_policy or DataPolicy(),
        )
        with self.database.transaction(immediate=True) as connection:
            self._insert_meta(connection, meta)
        return meta

    @staticmethod
    def _insert_meta(connection, meta: ProjectMeta) -> None:
        connection.execute(
            """
            INSERT INTO projects(
                id, name, created_at, script_text, market_json, owner_id, data_policy_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meta.id,
                meta.name,
                meta.created_at.isoformat(),
                meta.script_text,
                _json_dump(meta.market.model_dump(mode="json")),
                meta.owner_id,
                _json_dump(meta.data_policy.model_dump(mode="json")),
            ),
        )

    @staticmethod
    def _meta_from_row(row) -> ProjectMeta:
        return ProjectMeta.model_validate(
            {
                "id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "script_text": row["script_text"],
                "market": json.loads(row["market_json"]),
                "owner_id": row["owner_id"],
                "data_policy": json.loads(row["data_policy_json"]),
            }
        )

    def list_projects(self) -> list[ProjectMeta]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY created_at, id"
            ).fetchall()
        return [self._meta_from_row(row) for row in rows]

    def load_meta(self, project_id: str) -> ProjectMeta | None:
        self._peek_dir(project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return self._meta_from_row(row) if row is not None else None

    def delete_project(self, project_id: str) -> bool:
        self._peek_dir(project_id)
        with self.database.transaction(immediate=True) as connection:
            cursor = connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        artifact_dir = self.projects_dir / project_id
        if cursor.rowcount and artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        return cursor.rowcount > 0

    @staticmethod
    def _validated_state(payload: str | None) -> StoryState | None:
        if payload is None:
            return None
        try:
            state = StoryState.model_validate_json(payload)
        except ValidationError:
            return None
        if not state.scenes and not state.characters:
            return None
        return state

    def load_state(self, project_id: str) -> StoryState | None:
        self._peek_dir(project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM states WHERE project_id = ?", (project_id,)
            ).fetchone()
        return self._validated_state(row[0] if row is not None else None)

    def load_history_state(self, project_id: str, version: int) -> StoryState | None:
        self._peek_dir(project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM state_history
                WHERE project_id = ? AND version = ?
                """,
                (project_id, version),
            ).fetchone()
        return self._validated_state(row[0] if row is not None else None)

    def list_revisions(self, project_id: str) -> list[Revision]:
        state = self.load_state(project_id)
        if state is None:
            return []
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM revisions
                WHERE project_id = ? AND state_version <= ?
                ORDER BY revision_id
                """,
                (project_id, state.version),
            ).fetchall()
        return [
            Revision.model_validate(
                {
                    "revision_id": row["revision_id"],
                    "state_version": row["state_version"],
                    "kind": row["kind"],
                    "description": row["description"],
                    "changed_scene_ids": json.loads(row["changed_scene_ids_json"]),
                    "applied_option": (
                        json.loads(row["applied_option_json"])
                        if row["applied_option_json"] is not None
                        else None
                    ),
                    "created_at": row["created_at"],
                }
            )
            for row in rows
        ]

    def save_state(
        self,
        project_id: str,
        state: StoryState,
        kind: str,
        description: str = "",
        changed_scene_ids: list[str] | None = None,
        applied_option: dict | None = None,
        applied: AppliedAdaptation | list[AppliedAdaptation] | None = None,
    ) -> Revision:
        changed = changed_scene_ids or []
        with self.database.transaction(immediate=True) as connection:
            project = connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if project is None:
                raise KeyError(f"unknown project: {project_id}")
            row = connection.execute(
                "SELECT version FROM states WHERE project_id = ?", (project_id,)
            ).fetchone()
            next_version = (int(row[0]) if row is not None else 0) + 1
            candidate = state.model_copy(deep=True)
            candidate.version = next_version
            revision = Revision(
                revision_id=next_version,
                state_version=next_version,
                kind=kind,
                description=description,
                changed_scene_ids=changed,
                applied_option=applied_option,
            )
            state_payload = candidate.model_dump_json()
            connection.execute(
                """
                INSERT INTO state_history(project_id, version, payload_json)
                VALUES (?, ?, ?)
                """,
                (project_id, next_version, state_payload),
            )
            connection.execute(
                """
                INSERT INTO revisions(
                    project_id, revision_id, state_version, kind, description,
                    changed_scene_ids_json, applied_option_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    next_version,
                    next_version,
                    kind,
                    description,
                    _json_dump(changed),
                    _json_dump(applied_option) if applied_option is not None else None,
                    revision.created_at.isoformat(),
                ),
            )
            applied_items = []
            if applied is not None:
                applied_items = applied if isinstance(applied, list) else [applied]
                for item in applied_items:
                    payload = item.model_copy(deep=True)
                    payload.state_version = next_version
                    connection.execute(
                        """
                        INSERT INTO adaptations(
                            project_id, state_version, operation_id, payload_json
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            project_id,
                            next_version,
                            payload.operation_id,
                            payload.model_dump_json(),
                        ),
                    )
            connection.execute(
                """
                INSERT INTO states(project_id, version, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    version = excluded.version,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (project_id, next_version, state_payload, _now_text()),
            )
        state.version = next_version
        for item in applied_items:
            item.state_version = next_version
        return revision

    def save_plan(self, project_id: str, plan: AdaptationPlan) -> None:
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO plans(project_id, mechanism_id, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, mechanism_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    project_id,
                    plan.culture_mechanism_id,
                    plan.model_dump_json(),
                    _now_text(),
                ),
            )

    def load_plans(self, project_id: str) -> list[AdaptationPlan]:
        self._peek_dir(project_id)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM plans WHERE project_id = ? ORDER BY mechanism_id",
                (project_id,),
            ).fetchall()
        return [AdaptationPlan.model_validate_json(row[0]) for row in rows]

    def load_plan(self, project_id: str, mechanism_id: str) -> AdaptationPlan | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM plans
                WHERE project_id = ? AND mechanism_id = ?
                """,
                (project_id, mechanism_id),
            ).fetchone()
        return AdaptationPlan.model_validate_json(row[0]) if row is not None else None

    def append_applied(self, project_id: str, applied: AppliedAdaptation) -> None:
        state = self.load_state(project_id)
        if state is None:
            raise KeyError(f"unknown project state: {project_id}")
        if applied.state_version == 0:
            applied.state_version = state.version
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO adaptations(project_id, state_version, operation_id, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    project_id,
                    applied.state_version,
                    applied.operation_id,
                    applied.model_dump_json(),
                ),
            )

    def load_applied(self, project_id: str) -> list[AppliedAdaptation]:
        state = self.load_state(project_id)
        if state is None:
            return []
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM adaptations
                WHERE project_id = ? AND (state_version = 0 OR state_version <= ?)
                ORDER BY sequence_id
                """,
                (project_id, state.version),
            ).fetchall()
        return [AppliedAdaptation.model_validate_json(row[0]) for row in rows]

    def save_target_script(self, project_id: str, target_script: TargetScript) -> None:
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO target_scripts(
                    project_id, source_state_version, payload_json, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    source_state_version = excluded.source_state_version,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    project_id,
                    target_script.source_state_version,
                    target_script.model_dump_json(),
                    _now_text(),
                ),
            )

    def load_target_script(self, project_id: str) -> TargetScript | None:
        state = self.load_state(project_id)
        if state is None:
            return None
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT source_state_version, payload_json FROM target_scripts
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
        if row is None or int(row["source_state_version"]) != state.version:
            return None
        try:
            return TargetScript.model_validate_json(row["payload_json"])
        except ValidationError:
            return None

    def load_completed_analysis(
        self, project_id: str, analysis_key: str
    ) -> StoryState | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT merged_state_json FROM analysis_runs
                WHERE project_id = ? AND analysis_key = ? AND status = 'complete'
                """,
                (project_id, analysis_key),
            ).fetchone()
        return self._validated_state(row[0] if row is not None else None)

    def load_analysis_chunk(
        self,
        project_id: str,
        analysis_key: str,
        chunk_index: int,
        chunk_fingerprint: str,
    ) -> StoryState | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT state_json FROM analysis_chunks
                WHERE project_id = ? AND analysis_key = ? AND chunk_index = ?
                  AND chunk_fingerprint = ?
                """,
                (project_id, analysis_key, chunk_index, chunk_fingerprint),
            ).fetchone()
        if row is None:
            return None
        try:
            return StoryState.model_validate_json(row[0])
        except ValidationError:
            return None

    def save_analysis_chunk(
        self,
        project_id: str,
        analysis_key: str,
        chunk_index: int,
        chunk_fingerprint: str,
        total_chunks: int,
        state: StoryState,
    ) -> None:
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO analysis_runs(
                    project_id, analysis_key, status, total_chunks,
                    completed_chunks, merged_state_json, updated_at
                ) VALUES (?, ?, 'running', ?, 0, NULL, ?)
                ON CONFLICT(project_id, analysis_key) DO UPDATE SET
                    status = 'running',
                    total_chunks = excluded.total_chunks,
                    updated_at = excluded.updated_at
                """,
                (project_id, analysis_key, total_chunks, _now_text()),
            )
            connection.execute(
                """
                INSERT INTO analysis_chunks(
                    project_id, analysis_key, chunk_index, chunk_fingerprint,
                    state_json, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, analysis_key, chunk_index) DO UPDATE SET
                    chunk_fingerprint = excluded.chunk_fingerprint,
                    state_json = excluded.state_json,
                    completed_at = excluded.completed_at
                """,
                (
                    project_id,
                    analysis_key,
                    chunk_index,
                    chunk_fingerprint,
                    state.model_dump_json(),
                    _now_text(),
                ),
            )
            connection.execute(
                """
                UPDATE analysis_runs SET
                    completed_chunks = (
                        SELECT COUNT(*) FROM analysis_chunks
                        WHERE project_id = ? AND analysis_key = ?
                    ),
                    updated_at = ?
                WHERE project_id = ? AND analysis_key = ?
                """,
                (project_id, analysis_key, _now_text(), project_id, analysis_key),
            )

    def complete_analysis(
        self, project_id: str, analysis_key: str, state: StoryState
    ) -> None:
        with self.database.transaction(immediate=True) as connection:
            cursor = connection.execute(
                """
                UPDATE analysis_runs SET
                    status = 'complete',
                    completed_chunks = total_chunks,
                    merged_state_json = ?,
                    updated_at = ?
                WHERE project_id = ? AND analysis_key = ?
                """,
                (state.model_dump_json(), _now_text(), project_id, analysis_key),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"analysis checkpoint is missing: {project_id}")

    def import_legacy_projects(self, source_dir: Path) -> dict[str, int]:
        if not source_dir.exists():
            return {"imported": 0, "skipped": 0}
        legacy = ProjectStore(source_dir)
        imported = 0
        skipped = 0
        for directory in sorted(path for path in source_dir.iterdir() if path.is_dir()):
            try:
                meta = legacy.load_meta(directory.name)
            except (KeyError, ValidationError):
                continue
            if meta is None:
                continue
            source_key = f"legacy-project:{source_dir.resolve()}:{meta.id}"
            with self.database.transaction(immediate=True) as connection:
                seen = connection.execute(
                    "SELECT 1 FROM legacy_imports WHERE source_key = ?", (source_key,)
                ).fetchone()
                exists = connection.execute(
                    "SELECT 1 FROM projects WHERE id = ?", (meta.id,)
                ).fetchone()
                if seen is not None or exists is not None:
                    skipped += 1
                    if seen is None:
                        connection.execute(
                            """
                            INSERT INTO legacy_imports(source_key, imported_at, item_count)
                            VALUES (?, ?, 0)
                            """,
                            (source_key, _now_text()),
                        )
                    continue

                self._insert_meta(connection, meta)
                state = legacy.load_state(meta.id)
                revisions = legacy.list_revisions(meta.id)
                for revision in revisions:
                    snapshot = legacy.load_history_state(meta.id, revision.state_version)
                    if snapshot is not None:
                        connection.execute(
                            """
                            INSERT INTO state_history(project_id, version, payload_json)
                            VALUES (?, ?, ?)
                            """,
                            (meta.id, revision.state_version, snapshot.model_dump_json()),
                        )
                    connection.execute(
                        """
                        INSERT INTO revisions(
                            project_id, revision_id, state_version, kind, description,
                            changed_scene_ids_json, applied_option_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            meta.id,
                            revision.revision_id,
                            revision.state_version,
                            revision.kind,
                            revision.description,
                            _json_dump(revision.changed_scene_ids),
                            (
                                _json_dump(revision.applied_option)
                                if revision.applied_option is not None
                                else None
                            ),
                            revision.created_at.isoformat(),
                        ),
                    )
                if state is not None:
                    state_payload = state.model_dump_json()
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO state_history(project_id, version, payload_json)
                        VALUES (?, ?, ?)
                        """,
                        (meta.id, state.version, state_payload),
                    )
                    connection.execute(
                        """
                        INSERT INTO states(project_id, version, payload_json, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (meta.id, state.version, state_payload, _now_text()),
                    )
                for plan in legacy.load_plans(meta.id):
                    connection.execute(
                        """
                        INSERT INTO plans(project_id, mechanism_id, payload_json, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (meta.id, plan.culture_mechanism_id, plan.model_dump_json(), _now_text()),
                    )
                for item in legacy.load_applied(meta.id):
                    connection.execute(
                        """
                        INSERT INTO adaptations(
                            project_id, state_version, operation_id, payload_json
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (meta.id, item.state_version, item.operation_id, item.model_dump_json()),
                    )
                target = legacy.load_target_script(meta.id)
                if target is not None:
                    connection.execute(
                        """
                        INSERT INTO target_scripts(
                            project_id, source_state_version, payload_json, updated_at
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            meta.id,
                            target.source_state_version,
                            target.model_dump_json(),
                            _now_text(),
                        ),
                    )
                connection.execute(
                    """
                    INSERT INTO legacy_imports(source_key, imported_at, item_count)
                    VALUES (?, ?, 1)
                    """,
                    (source_key, _now_text()),
                )
            imported += 1
        return {"imported": imported, "skipped": skipped}
