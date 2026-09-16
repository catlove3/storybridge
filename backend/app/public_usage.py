"""Durable admission and per-attempt accounting, shared by every model entrypoint."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.config import ShareConfig, get_config
from app.database import SQLiteDatabase


class PublicLimitError(RuntimeError):
    def __init__(self, code: str, message: str, resets_at: str | None = None):
        super().__init__(message)
        self.code = code
        self.resets_at = resets_at

    def detail(self) -> dict:
        return {"code": self.code, "message": str(self), "resets_at": self.resets_at}


class PublicUsage:
    def __init__(self, database: SQLiteDatabase, config: ShareConfig, clock=time.time):
        self.database = database
        self.config = config
        self.clock = clock

    def period(self) -> tuple[str, str]:
        now = datetime.fromtimestamp(self.clock(), ZoneInfo("Asia/Shanghai"))
        reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return now.date().isoformat(), reset.isoformat()

    def _totals(self, connection, owner: str, day: str) -> tuple[int, int]:
        row = connection.execute(
            """SELECT COALESCE(SUM(CASE WHEN owner_id=? THEN tokens ELSE 0 END),0),
               COALESCE(SUM(tokens),0) FROM token_reservations WHERE day=?""",
            (owner, day),
        ).fetchone()
        return int(row[0]), int(row[1])

    def _check(self, totals: tuple[int, int], additional: int, resets: str) -> None:
        for used, limit, scope, label in (
            (totals[0], self.config.visitor_daily_tokens, "visitor", "你今天的体验额度"),
            (totals[1], self.config.site_daily_tokens, "site", "今天的全站体验额度"),
        ):
            if used + additional > limit:
                raise PublicLimitError(
                    f"{scope}_daily_quota",
                    f"{label}不足以继续生成，已完成内容仍可查看和下载。",
                    resets,
                )

    def status(self, owner: str) -> dict:
        day, resets = self.period()
        with self.database.transaction() as connection:
            visitor, site = self._totals(connection, owner, day)
        return {
            "visitor_used": visitor,
            "visitor_limit": self.config.visitor_daily_tokens,
            "site_used": site,
            "site_limit": self.config.site_daily_tokens,
            "resets_at": resets,
        }

    def reserve(self, owner: str, tokens: int) -> str:
        if not owner or tokens <= 0:
            raise ValueError("a positive reservation and owner are required")
        day, resets = self.period()
        identifier = uuid.uuid4().hex
        with self.database.transaction(immediate=True) as connection:
            self._check(self._totals(connection, owner, day), tokens, resets)
            connection.execute(
                "INSERT INTO token_reservations(id,owner_id,day,tokens,created_at) VALUES(?,?,?,?,?)",
                (identifier, owner, day, tokens, self.clock()),
            )
        return identifier

    def settle(self, identifier: str, actual: int | None) -> None:
        # Unknown outcome keeps the full reservation, including across crashes.
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                """UPDATE token_reservations SET tokens=COALESCE(?,tokens), settled=1
                   WHERE id=? AND settled=0""",
                (actual, identifier),
            )

    def admit(self, owner: str) -> str:
        now = self.clock()
        day, resets = self.period()
        identifier = uuid.uuid4().hex
        with self.database.transaction(immediate=True) as connection:
            self._check(self._totals(connection, owner, day), 1, resets)
            rows = connection.execute(
                "SELECT owner_id,created_at,active FROM generation_slots WHERE active=1 OR created_at>?",
                (now - 60,),
            ).fetchall()
            for scope, label, subset, concurrent, rate in (
                (
                    "visitor",
                    "你",
                    [r for r in rows if r["owner_id"] == owner],
                    self.config.visitor_concurrency,
                    self.config.visitor_submissions_per_minute,
                ),
                (
                    "site",
                    "本站",
                    rows,
                    self.config.site_concurrency,
                    self.config.site_submissions_per_minute,
                ),
            ):
                if sum(r["active"] for r in subset) >= concurrent:
                    raise PublicLimitError(
                        f"{scope}_concurrency", f"{label}还有生成正在进行，请稍后重试。"
                    )
                recent = [r["created_at"] for r in subset if r["created_at"] > now - 60]
                if len(recent) >= rate:
                    reset = datetime.fromtimestamp(min(recent) + 60, ZoneInfo("Asia/Shanghai"))
                    raise PublicLimitError(
                        f"{scope}_rate_limit", "提交较频繁，请稍后重试。", reset.isoformat()
                    )
            connection.execute(
                "INSERT INTO generation_slots(id,owner_id,created_at) VALUES(?,?,?)",
                (identifier, owner, now),
            )
            connection.execute(
                "DELETE FROM generation_slots WHERE active=0 AND created_at<?", (now - 60,)
            )
        return identifier

    def release(self, identifier: str) -> None:
        with self.database.transaction(immediate=True) as connection:
            connection.execute("UPDATE generation_slots SET active=0 WHERE id=?", (identifier,))

    def recover(self) -> None:
        # Single worker only. Jobs are marked interrupted by JobManager at startup.
        with self.database.transaction(immediate=True) as connection:
            connection.execute("UPDATE generation_slots SET active=0")


@lru_cache
def _usage(path: str, config_json: str) -> PublicUsage:
    from pathlib import Path

    return PublicUsage(SQLiteDatabase(Path(path)), ShareConfig.model_validate_json(config_json))


def public_usage() -> PublicUsage:
    config = get_config()
    return _usage(str(config.storage.database_file), config.share.model_dump_json())
