"""Offline map-data providers and the normalized local SQLite cache."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import closing
from pathlib import Path
import sqlite3

from .models import MapCoordinate, MobSpawn


class MapDataProvider(ABC):
    """Source-independent interface for querying target mob spawns."""

    @abstractmethod
    def query_target_mob_locations(
        self,
        target_mob: str,
        *,
        state_id: int | None = None,
        floor_id: str | None = None,
    ) -> tuple[MobSpawn, ...]:
        """Return raw locations for an exact mob id or name."""


class KuroMapDataProvider(MapDataProvider):
    """Read the Kuro/Kurobbs ``map_items.db`` schema without extra packages."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)

    def query_target_mob_locations(
        self,
        target_mob: str,
        *,
        state_id: int | None = None,
        floor_id: str | None = None,
    ) -> tuple[MobSpawn, ...]:
        query = """
            SELECT location.id, item.id, item.name, location.state_id,
                   location.floor_id, location.x, location.y,
                   location.description
            FROM location
            JOIN item ON item.id = location.item_id
            WHERE (item.id = ? OR item.name = ? COLLATE NOCASE)
              AND location.x IS NOT NULL
              AND location.y IS NOT NULL
        """
        params: list[object] = [str(target_mob), str(target_mob)]
        if state_id is not None:
            query += " AND location.state_id = ?"
            params.append(state_id)
        if floor_id is not None:
            query += " AND location.floor_id = ?"
            params.append(floor_id)
        query += " ORDER BY location.state_id, location.floor_id, location.id"

        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(_spawn_from_row(row) for row in rows)

    def populate_cache(self, cache: "NormalizedMapCache") -> None:
        """Import the Kuro schema into a local, dependency-free cache."""
        cache.replace_from_kuro_database(self.database_path)


class NormalizedMapCache:
    """Small normalized cache used by offline planning and future refreshes."""

    SCHEMA = """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS mob (
            mob_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT
        );
        CREATE TABLE IF NOT EXISTS spawn (
            spawn_id TEXT PRIMARY KEY,
            mob_id TEXT NOT NULL REFERENCES mob(mob_id),
            state_id INTEGER NOT NULL,
            floor_id TEXT NOT NULL,
            x REAL NOT NULL,
            y REAL NOT NULL,
            description TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_spawn_mob_layer
            ON spawn(mob_id, state_id, floor_id);
    """

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        with closing(self._connect()) as connection, connection:
            connection.executescript(self.SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def replace_from_kuro_database(self, source_path: str | Path) -> None:
        with closing(sqlite3.connect(str(source_path))) as source:
            mobs = source.execute("SELECT id, name, icon FROM item ORDER BY id").fetchall()
            spawns = source.execute(
                """
                SELECT id, item_id, state_id, COALESCE(floor_id, ''), x, y,
                       COALESCE(description, '')
                FROM location
                WHERE x IS NOT NULL AND y IS NOT NULL
                ORDER BY id
                """
            ).fetchall()

        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM spawn")
            connection.execute("DELETE FROM mob")
            connection.executemany("INSERT INTO mob VALUES (?, ?, ?)", mobs)
            connection.executemany("INSERT INTO spawn VALUES (?, ?, ?, ?, ?, ?, ?)", spawns)

    def query_target_mob_locations(
        self,
        target_mob: str,
        *,
        state_id: int | None = None,
        floor_id: str | None = None,
    ) -> tuple[MobSpawn, ...]:
        query = """
            SELECT spawn.spawn_id, mob.mob_id, mob.name, spawn.state_id,
                   spawn.floor_id, spawn.x, spawn.y, spawn.description
            FROM spawn JOIN mob ON mob.mob_id = spawn.mob_id
            WHERE (mob.mob_id = ? OR mob.name = ? COLLATE NOCASE)
        """
        params: list[object] = [str(target_mob), str(target_mob)]
        if state_id is not None:
            query += " AND spawn.state_id = ?"
            params.append(state_id)
        if floor_id is not None:
            query += " AND spawn.floor_id = ?"
            params.append(floor_id)
        query += " ORDER BY spawn.state_id, spawn.floor_id, spawn.spawn_id"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(_spawn_from_row(row) for row in rows)


class LocalMapDataProvider(MapDataProvider):
    """Provider backed by :class:`NormalizedMapCache`."""

    def __init__(self, cache: NormalizedMapCache):
        self.cache = cache

    def query_target_mob_locations(
        self,
        target_mob: str,
        *,
        state_id: int | None = None,
        floor_id: str | None = None,
    ) -> tuple[MobSpawn, ...]:
        return self.cache.query_target_mob_locations(
            target_mob, state_id=state_id, floor_id=floor_id
        )


def _spawn_from_row(row: tuple[object, ...]) -> MobSpawn:
    spawn_id, mob_id, mob_name, state_id, floor_id, x, y, description = row
    return MobSpawn(
        spawn_id=str(spawn_id),
        mob_id=str(mob_id),
        mob_name=str(mob_name),
        state_id=int(state_id),
        floor_id=str(floor_id or ""),
        coordinate=MapCoordinate(float(x), float(y)),
        description=str(description or ""),
    )
