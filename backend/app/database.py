from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path

Migration = tuple[int, str, tuple[str, ...]]

MIGRATIONS: tuple[Migration, ...] = (
    (
        1,
        "project storage",
        (
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                script_text TEXT NOT NULL,
                market_json TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                data_policy_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE states (
                project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                version INTEGER NOT NULL CHECK (version >= 1),
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE state_history (
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                version INTEGER NOT NULL CHECK (version >= 1),
                payload_json TEXT NOT NULL,
                PRIMARY KEY (project_id, version)
            )
            """,
            """
            CREATE TABLE revisions (
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                revision_id INTEGER NOT NULL,
                state_version INTEGER NOT NULL,
                kind TEXT NOT NULL,
                description TEXT NOT NULL,
                changed_scene_ids_json TEXT NOT NULL,
                applied_option_json TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, revision_id)
            )
            """,
            """
            CREATE TABLE plans (
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                mechanism_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (project_id, mechanism_id)
            )
            """,
            """
            CREATE TABLE adaptations (
                sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                state_version INTEGER NOT NULL,
                operation_id TEXT,
                payload_json TEXT NOT NULL
            )
            """,
            "CREATE INDEX adaptations_project_version ON adaptations(project_id, state_version)",
            """
            CREATE TABLE target_scripts (
                project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                source_state_version INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    (
        2,
        "durable jobs and legacy import ledger",
        (
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                finished_at REAL,
                result_json TEXT,
                error TEXT,
                idempotency_key TEXT,
                progress REAL NOT NULL,
                cancel_requested INTEGER NOT NULL
            )
            """,
            "CREATE INDEX jobs_project_created ON jobs(project_id, created_at)",
            """
            CREATE UNIQUE INDEX jobs_project_idempotency
            ON jobs(project_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """,
            """
            CREATE TABLE legacy_imports (
                source_key TEXT PRIMARY KEY,
                imported_at TEXT NOT NULL,
                item_count INTEGER NOT NULL
            )
            """,
        ),
    ),
)


class MigrationError(RuntimeError):
    pass


class SQLiteDatabase:
    def __init__(
        self,
        path: Path,
        *,
        migrations: Iterable[Migration] = MIGRATIONS,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self.migrations = tuple(migrations)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self.timeout_seconds,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute(f"PRAGMA busy_timeout = {int(self.timeout_seconds * 1000)}")
        return connection

    @contextmanager
    def transaction(self, *, immediate: bool = False):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        latest = max((version for version, _, _ in self.migrations), default=0)
        while True:
            with self.transaction(immediate=True) as connection:
                current = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                    ).fetchone()[0]
                )
                if current > latest:
                    raise MigrationError(
                        f"database schema {current} is newer than supported schema {latest}"
                    )
                pending = next(
                    (migration for migration in self.migrations if migration[0] > current),
                    None,
                )
                if pending is None:
                    return
                version, name, statements = pending
                if version != current + 1:
                    raise MigrationError(
                        f"missing migration between schema {current} and {version}"
                    )
                for statement in statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                    (version, name),
                )

    def schema_version(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()
        return int(row[0])

    def journal_mode(self) -> str:
        with self.connect() as connection:
            row = connection.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]).lower()

    def quick_check(self) -> bool:
        with self.connect() as connection:
            row = connection.execute("PRAGMA quick_check").fetchone()
        return row is not None and row[0] == "ok"
