from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.database import MIGRATIONS, SQLiteDatabase
from app.schemas import AdaptationPlan, StoryState
from app.sqlite_storage import SQLiteProjectStore
from app.storage import MarketProfile, ProjectStore
from tests.fixtures import sample_story_state_dict


def _store(tmp_path) -> SQLiteProjectStore:
    return SQLiteProjectStore(tmp_path / "storybridge.sqlite3", tmp_path / "artifacts")


def test_schema_upgrade_and_wal_mode(tmp_path):
    path = tmp_path / "upgrade.sqlite3"
    first_version = SQLiteDatabase(path, migrations=MIGRATIONS[:1])
    assert first_version.schema_version() == 1

    upgraded = SQLiteDatabase(path)
    assert upgraded.schema_version() == 2
    assert upgraded.journal_mode() == "wal"
    assert upgraded.quick_check() is True
    with upgraded.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"projects", "states", "state_history", "jobs", "legacy_imports"} <= tables


def test_failed_migration_rolls_back_only_that_version(tmp_path):
    path = tmp_path / "rollback-migration.sqlite3"
    migrations = (
        (1, "stable", ("CREATE TABLE stable(value TEXT)",)),
        (
            2,
            "broken",
            (
                "CREATE TABLE must_rollback(value TEXT)",
                "INSERT INTO table_that_does_not_exist VALUES (1)",
            ),
        ),
    )
    with pytest.raises(sqlite3.OperationalError):
        SQLiteDatabase(path, migrations=migrations)

    with sqlite3.connect(path) as connection:
        version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        stable = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'stable'"
        ).fetchone()
        rolled_back = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'must_rollback'"
        ).fetchone()
    assert version == 1
    assert stable == (1,)
    assert rolled_back is None


def test_state_revision_and_history_commit_atomically(tmp_path):
    store = _store(tmp_path)
    meta = store.create_project("atomic", "script", MarketProfile())
    original = StoryState.model_validate(sample_story_state_dict())
    store.save_state(meta.id, original, "initial_parse")

    with store.database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_second_revision
            BEFORE INSERT ON revisions
            WHEN NEW.state_version = 2
            BEGIN
                SELECT RAISE(ABORT, 'simulated revision failure');
            END
            """
        )

    candidate = original.model_copy(deep=True)
    candidate.scene_by_id("S01").text = "must not commit"
    with pytest.raises(sqlite3.IntegrityError, match="simulated revision failure"):
        store.save_state(meta.id, candidate, "adaptation_applied")

    committed = store.load_state(meta.id)
    assert committed is not None
    assert committed.version == 1
    assert committed.scene_by_id("S01").text != "must not commit"
    assert store.load_history_state(meta.id, 2) is None
    assert [revision.state_version for revision in store.list_revisions(meta.id)] == [1]


def test_concurrent_writers_receive_contiguous_versions(tmp_path):
    store = _store(tmp_path)
    meta = store.create_project("concurrent", "script", MarketProfile())
    base = StoryState.model_validate(sample_story_state_dict())

    def save(index: int) -> int:
        candidate = base.model_copy(deep=True)
        candidate.scene_by_id("S01").text = f"writer-{index}"
        return store.save_state(meta.id, candidate, "repair").state_version

    with ThreadPoolExecutor(max_workers=8) as executor:
        versions = list(executor.map(save, range(12)))

    assert sorted(versions) == list(range(1, 13))
    assert store.load_state(meta.id).version == 12
    assert len(store.list_revisions(meta.id)) == 12


def test_legacy_json_import_is_complete_and_idempotent(tmp_path):
    legacy_dir = tmp_path / "legacy-projects"
    legacy = ProjectStore(legacy_dir)
    meta = legacy.create_project(
        "legacy",
        "真实旧项目文本",
        MarketProfile(market="United States", audience="18-30"),
        owner_id="owner-a",
    )
    state = StoryState.model_validate(sample_story_state_dict())
    legacy.save_state(meta.id, state, "initial_parse", description="legacy revision")
    fixture = {
        "culture_mechanism_id": "CM01",
        "original_name": "编制",
        "friction_level": "high",
        "options": [
            {
                "option_label": label,
                "strategy": strategy,
                "title": label,
                "replacement_definition": label,
                "rationale": label,
            }
            for label, strategy in (
                ("A", "preserve"),
                ("B", "functional_replacement"),
                ("C", "plot_reconstruction"),
            )
        ],
    }
    legacy.save_plan(meta.id, AdaptationPlan.model_validate(fixture))

    sqlite_store = _store(tmp_path)
    first = sqlite_store.import_legacy_projects(legacy_dir)
    second = sqlite_store.import_legacy_projects(legacy_dir)

    assert first == {"imported": 1, "skipped": 0}
    assert second == {"imported": 0, "skipped": 1}
    imported_meta = sqlite_store.load_meta(meta.id)
    assert imported_meta is not None
    assert imported_meta.script_text == "真实旧项目文本"
    assert imported_meta.owner_id == "owner-a"
    assert sqlite_store.load_state(meta.id).model_dump() == state.model_dump()
    assert sqlite_store.load_history_state(meta.id, 1) is not None
    assert sqlite_store.load_plan(meta.id, "CM01") is not None
