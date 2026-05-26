from __future__ import annotations

from mcp.server.fastmcp import FastMCP

try:
    from .cbdb_sqlite import CBDBSQLite
except ImportError:
    from cbdb_sqlite import CBDBSQLite


mcp = FastMCP("cbdb-mcp-annotation-demo")
db = CBDBSQLite()


@mcp.tool()
def inspect_schema() -> dict:
    """Inspect available CBDB SQLite tables, views, columns, and recommended objects."""
    return db.inspect_schema()


@mcp.tool()
def search_person(name: str, limit: int = 10) -> list[dict]:
    """Search CBDB person records by Chinese name, romanized name, or alternate names."""
    return db.search_person(name, limit)


@mcp.tool()
def search_place(name: str, limit: int = 10) -> list[dict]:
    """Search CBDB place records by Chinese or romanized place name."""
    return db.search_place(name, limit)


@mcp.tool()
def search_office(name: str, limit: int = 10) -> list[dict]:
    """Search CBDB office records by Chinese office title, pinyin, or translation."""
    return db.search_office(name, limit)


@mcp.tool()
def search_reign(name: str, limit: int = 10) -> list[dict]:
    """Search CBDB reign-period records by Chinese reign title or pinyin."""
    return db.search_reign(name, limit)


@mcp.tool()
def resolve_entity(name: str, entity_type: str, limit: int = 10) -> list[dict]:
    """Resolve an entity using person, place, office, reign, or auto search."""
    return db.resolve_entity(name, entity_type, limit)


if __name__ == "__main__":
    mcp.run()
