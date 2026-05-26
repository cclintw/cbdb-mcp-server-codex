from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DB_PATH = Path("data/cbdb/cbdb.sqlite")
CBDB_PERSON_URL = "https://cbdb.fas.harvard.edu/cbdbapi/person?id={person_id}"


@dataclass
class QueryContext:
    db_path: Path
    exists: bool


def get_db_path() -> Path:
    return Path(os.environ.get("CBDB_SQLITE_PATH", DEFAULT_DB_PATH)).expanduser()


class CBDBSQLite:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path).expanduser() if db_path else get_db_path()

    def context(self) -> QueryContext:
        return QueryContext(db_path=self.db_path, exists=self.db_path.exists())

    def connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(f"CBDB SQLite not found: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def inspect_schema(self) -> dict[str, Any]:
        ctx = self.context()
        if not ctx.exists:
            return {
                "db_path": str(ctx.db_path),
                "sqlite_exists": False,
                "tables": [],
                "views": [],
                "columns": {},
                "has_View_PeopleData": False,
                "has_View_PostingOfficeData": False,
                "has_ADDRESSES": False,
                "has_ADDR_CODES": False,
                "has_OFFICE_CODES": False,
                "has_NIAN_HAO": False,
                "error": f"CBDB SQLite not found: {ctx.db_path}",
            }

        with self.connect() as conn:
            objects = conn.execute(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY type, name"
            ).fetchall()
            tables = [row["name"] for row in objects if row["type"] == "table"]
            views = [row["name"] for row in objects if row["type"] == "view"]
            columns: dict[str, list[str]] = {}
            for object_name in tables + views:
                columns[object_name] = [row["name"] for row in conn.execute(f'PRAGMA table_info("{object_name}")')]

        names = set(tables + views)
        return {
            "db_path": str(ctx.db_path),
            "sqlite_exists": True,
            "tables": tables,
            "views": views,
            "columns": columns,
            "has_View_PeopleData": "View_PeopleData" in names,
            "has_View_PostingOfficeData": "View_PostingOfficeData" in names,
            "has_ADDRESSES": "ADDRESSES" in names,
            "has_ADDR_CODES": "ADDR_CODES" in names,
            "has_OFFICE_CODES": "OFFICE_CODES" in names,
            "has_NIAN_HAO": "NIAN_HAO" in names,
        }

    def search_person(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        name = normalize_search(name)
        if not name:
            return []
        return self._safe_search(lambda conn: self._search_person(conn, name, safe_limit(limit)))

    def search_place(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        name = normalize_search(name)
        if not name:
            return []
        return self._safe_search(lambda conn: self._search_place(conn, name, safe_limit(limit)))

    def search_office(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        name = normalize_search(name)
        if not name:
            return []
        return self._safe_search(lambda conn: self._search_office(conn, name, safe_limit(limit)))

    def search_reign(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        name = normalize_search(name)
        if not name:
            return []
        return self._safe_search(lambda conn: self._search_reign(conn, name, safe_limit(limit)))

    def resolve_entity(self, name: str, entity_type: str, limit: int = 10) -> list[dict[str, Any]]:
        entity_type = (entity_type or "auto").strip().lower()
        if entity_type == "person":
            return self.search_person(name, limit)
        if entity_type == "place":
            return self.search_place(name, limit)
        if entity_type == "office":
            return self.search_office(name, limit)
        if entity_type == "reign":
            return self.search_reign(name, limit)
        if entity_type == "auto":
            results: list[dict[str, Any]] = []
            for search in (self.search_person, self.search_place, self.search_office, self.search_reign):
                results.extend(search(name, limit))
                if len(results) >= limit:
                    break
            return results[: safe_limit(limit)]
        return [{"error": f"Unsupported entity_type: {entity_type}", "allowed": ["auto", "person", "place", "office", "reign"]}]

    def _safe_search(self, search_fn: Any) -> list[dict[str, Any]]:
        try:
            with self.connect() as conn:
                return search_fn(conn)
        except FileNotFoundError as exc:
            return [{"error": str(exc)}]
        except sqlite3.Error as exc:
            return [{"error": f"SQLite error: {exc}"}]

    def _search_person(self, conn: sqlite3.Connection, name: str, limit: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        like = like_param(name)

        if has_table(conn, "View_PeopleData"):
            cols = columns(conn, "View_PeopleData")
            name_cols = existing(cols, ["c_name_chn", "c_name", "c_alt_name_chn", "c_alt_name"])
            select_cols = existing(cols, ["c_personid", "c_name_chn", "c_name", "c_index_year", "c_birthyear", "c_deathyear", "c_dynasty_chn", "c_dynasty", "c_dy"])
            if name_cols and {"c_personid"}.issubset(cols):
                rows = select_like(conn, "View_PeopleData", select_cols, name_cols, like, limit)
                for row in rows:
                    add_unique(results, seen, map_person(row, matched_name(name, row, name_cols)))
                    if len(results) >= limit:
                        return results

        if has_table(conn, "BIOG_MAIN"):
            cols = columns(conn, "BIOG_MAIN")
            name_cols = existing(cols, ["c_name_chn", "c_name"])
            select_cols = existing(cols, ["c_personid", "c_name_chn", "c_name", "c_index_year", "c_birthyear", "c_deathyear", "c_dy"])
            if name_cols and {"c_personid"}.issubset(cols):
                rows = select_like(conn, "BIOG_MAIN", select_cols, name_cols, like, limit)
                for row in rows:
                    add_unique(results, seen, map_person(with_dynasty(conn, row), matched_name(name, row, name_cols)))
                    if len(results) >= limit:
                        return results

        if has_table(conn, "ALTNAME_DATA") and has_table(conn, "BIOG_MAIN"):
            alt_cols = columns(conn, "ALTNAME_DATA")
            bio_cols = columns(conn, "BIOG_MAIN")
            name_cols = existing(alt_cols, ["c_alt_name_chn", "c_alt_name"])
            if name_cols and {"c_personid"}.issubset(alt_cols) and {"c_personid"}.issubset(bio_cols):
                conditions = " OR ".join([f"a.{col} LIKE ?" for col in name_cols])
                sql = f"""
                    SELECT a.c_alt_name_chn, a.c_alt_name, b.c_personid, b.c_name_chn, b.c_name,
                           b.c_index_year, b.c_birthyear, b.c_deathyear, b.c_dy
                    FROM ALTNAME_DATA a
                    JOIN BIOG_MAIN b ON a.c_personid = b.c_personid
                    WHERE {conditions}
                    LIMIT ?
                """
                rows = conn.execute(sql, (*([like] * len(name_cols)), limit)).fetchall()
                for row in rows:
                    add_unique(results, seen, map_person(with_dynasty(conn, row), matched_name(name, row, name_cols)))
                    if len(results) >= limit:
                        break

        return results

    def _search_place(self, conn: sqlite3.Connection, name: str, limit: int) -> list[dict[str, Any]]:
        like = like_param(name)
        if has_table(conn, "ADDRESSES"):
            cols = columns(conn, "ADDRESSES")
            name_cols = existing(cols, ["c_name_chn", "c_name", "name_chn", "name"])
            id_col = first_existing(cols, ["c_addr_id", "addr_id"])
            if name_cols and id_col:
                select_cols = existing(cols, ["c_addr_id", "addr_id", "c_name_chn", "c_name", "name_chn", "name", "x_coord", "y_coord", "admin_type", "admin_level", "belongs_to", "parent_id"])
                return [map_place(row, matched_name(name, row, name_cols)) for row in select_like(conn, "ADDRESSES", select_cols, name_cols, like, limit)]

        if has_table(conn, "ADDR_CODES"):
            cols = columns(conn, "ADDR_CODES")
            name_cols = existing(cols, ["c_name_chn", "c_name"])
            if name_cols and "c_addr_id" in cols:
                select_cols = existing(cols, ["c_addr_id", "c_name_chn", "c_name", "x_coord", "y_coord"])
                return [map_place(row, matched_name(name, row, name_cols)) for row in select_like(conn, "ADDR_CODES", select_cols, name_cols, like, limit)]

        if has_table(conn, "View_PeopleAddrData"):
            cols = columns(conn, "View_PeopleAddrData")
            name_cols = existing(cols, ["c_addr_chn", "c_name_chn", "c_addr", "c_name"])
            id_col = first_existing(cols, ["c_addr_id", "addr_id"])
            if name_cols and id_col:
                select_cols = existing(cols, [id_col, *name_cols, "x_coord", "y_coord"])
                return [map_place(row, matched_name(name, row, name_cols)) for row in select_like(conn, "View_PeopleAddrData", select_cols, name_cols, like, limit)]
        return []

    def _search_office(self, conn: sqlite3.Connection, name: str, limit: int) -> list[dict[str, Any]]:
        like = like_param(name)
        if has_table(conn, "View_PostingOfficeData"):
            cols = columns(conn, "View_PostingOfficeData")
            name_cols = existing(cols, ["c_office_chn", "c_office_pinyin", "c_office_trans"])
            id_col = first_existing(cols, ["c_office_id", "office_id"])
            if name_cols and id_col:
                select_cols = existing(cols, [id_col, "c_office_chn", "c_office_pinyin", "c_office_trans"])
                return [map_office(row, matched_name(name, row, name_cols)) for row in select_like(conn, "View_PostingOfficeData", select_cols, name_cols, like, limit)]

        if has_table(conn, "OFFICE_CODES"):
            cols = columns(conn, "OFFICE_CODES")
            name_cols = existing(cols, ["c_office_chn", "c_office_pinyin", "c_office_trans"])
            if name_cols and "c_office_id" in cols:
                select_cols = existing(cols, ["c_office_id", "c_office_chn", "c_office_pinyin", "c_office_trans"])
                return [map_office(row, matched_name(name, row, name_cols)) for row in select_like(conn, "OFFICE_CODES", select_cols, name_cols, like, limit)]
        return []

    def _search_reign(self, conn: sqlite3.Connection, name: str, limit: int) -> list[dict[str, Any]]:
        if not has_table(conn, "NIAN_HAO"):
            return []
        cols = columns(conn, "NIAN_HAO")
        name_cols = existing(cols, ["c_nianhao_chn", "c_nianhao_pin"])
        if not name_cols or "c_nianhao_id" not in cols:
            return []
        select_cols = existing(cols, ["c_nianhao_id", "c_nianhao_chn", "c_nianhao_pin", "c_dy"])
        rows = select_like(conn, "NIAN_HAO", select_cols, name_cols, like_param(name), limit)
        return [map_reign(with_dynasty(conn, row), matched_name(name, row, name_cols)) for row in rows]


def normalize_search(value: str) -> str:
    return (value or "").strip()


def safe_limit(limit: int) -> int:
    try:
        return max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        return 10


def like_param(name: str) -> str:
    return f"%{name}%"


def has_table(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('table', 'view') LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table_name}")')}


def existing(cols: set[str], names: Iterable[str]) -> list[str]:
    return [name for name in names if name in cols]


def first_existing(cols: set[str], names: Iterable[str]) -> str | None:
    return next((name for name in names if name in cols), None)


def select_like(
    conn: sqlite3.Connection,
    table_name: str,
    select_cols: list[str],
    name_cols: list[str],
    like: str,
    limit: int,
) -> list[sqlite3.Row]:
    quoted_select = ", ".join([f'"{col}"' for col in select_cols])
    where = " OR ".join([f'"{col}" LIKE ?' for col in name_cols])
    sql = f'SELECT {quoted_select} FROM "{table_name}" WHERE {where} LIMIT ?'
    return conn.execute(sql, (*([like] * len(name_cols)), limit)).fetchall()


def matched_name(query: str, row: sqlite3.Row, name_cols: Iterable[str]) -> str:
    row_keys = set(row.keys())
    for col in name_cols:
        if col in row_keys and row[col] and query in str(row[col]):
            return str(row[col])
    for col in name_cols:
        if col in row_keys and row[col]:
            return str(row[col])
    return query


def value(row: sqlite3.Row | dict[str, Any], *keys: str) -> Any:
    row_keys = set(row.keys())
    for key in keys:
        if key in row_keys and row[key] not in (None, ""):
            return row[key]
    return None


def with_dynasty(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    if value(data, "c_dynasty_chn", "c_dynasty"):
        return data
    dy = value(data, "c_dy")
    if dy is None or not has_table(conn, "DYNASTIES"):
        return data
    cols = columns(conn, "DYNASTIES")
    if not {"c_dy"}.issubset(cols):
        return data
    select_cols = existing(cols, ["c_dynasty_chn", "c_dynasty"])
    if not select_cols:
        return data
    sql = f'SELECT {", ".join(select_cols)} FROM DYNASTIES WHERE c_dy = ? LIMIT 1'
    dynasty = conn.execute(sql, (dy,)).fetchone()
    if dynasty:
        data.update(dict(dynasty))
    return data


def map_person(row: sqlite3.Row | dict[str, Any], matched: str) -> dict[str, Any]:
    person_id = value(row, "c_personid")
    canonical = value(row, "c_name_chn", "c_name", "c_alt_name_chn", "c_alt_name") or matched
    return {
        "entity_type": "person",
        "canonical_name": canonical,
        "matched_name": matched,
        "source": "CBDB",
        "source_id": str(person_id) if person_id is not None else None,
        "index_year": value(row, "c_index_year"),
        "birth_year": value(row, "c_birthyear"),
        "death_year": value(row, "c_deathyear"),
        "dynasty": value(row, "c_dynasty_chn", "c_dynasty", "c_dy"),
        "source_url": CBDB_PERSON_URL.format(person_id=person_id) if person_id is not None else None,
    }


def map_place(row: sqlite3.Row | dict[str, Any], matched: str) -> dict[str, Any]:
    addr_id = value(row, "c_addr_id", "addr_id")
    canonical = value(row, "c_name_chn", "name_chn", "c_name", "name", "c_addr_chn", "c_addr") or matched
    result = {
        "entity_type": "place",
        "canonical_name": canonical,
        "matched_name": matched,
        "source": "CBDB",
        "source_id": str(addr_id) if addr_id is not None else None,
        "x_coord": value(row, "x_coord"),
        "y_coord": value(row, "y_coord"),
    }
    for key in ("admin_type", "admin_level", "belongs_to", "parent_id"):
        if value(row, key) is not None:
            result[key] = value(row, key)
    return result


def map_office(row: sqlite3.Row | dict[str, Any], matched: str) -> dict[str, Any]:
    office_id = value(row, "c_office_id", "office_id")
    return {
        "entity_type": "office",
        "canonical_name": value(row, "c_office_chn", "c_office_pinyin", "c_office_trans") or matched,
        "matched_name": matched,
        "source": "CBDB",
        "source_id": str(office_id) if office_id is not None else None,
        "office_pinyin": value(row, "c_office_pinyin"),
        "office_translation": value(row, "c_office_trans"),
    }


def map_reign(row: sqlite3.Row | dict[str, Any], matched: str) -> dict[str, Any]:
    reign_id = value(row, "c_nianhao_id")
    return {
        "entity_type": "reign",
        "canonical_name": value(row, "c_nianhao_chn", "c_nianhao_pin") or matched,
        "matched_name": matched,
        "source": "CBDB",
        "source_id": str(reign_id) if reign_id is not None else None,
        "dynasty": value(row, "c_dynasty_chn", "c_dynasty", "c_dy"),
    }


def add_unique(results: list[dict[str, Any]], seen: set[tuple[str, str]], item: dict[str, Any]) -> None:
    key = (item.get("entity_type") or "", item.get("source_id") or item.get("matched_name") or "")
    if key not in seen:
        seen.add(key)
        results.append(item)
