from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path("data/cbdb/cbdb.sqlite")
INPUT_PATH = Path("data/input/sample-1.txt")
AUTHORITY_PATH = Path("data/output/authority_table.json")
PERSON_URL = "https://cbdb.fas.harvard.edu/cbdbapi/person?id={person_id}"
RANDOM_SEED = 20260526


CHINESE_NUMBERS = "零一二三四五六七八九"
FORBIDDEN_NAME_PARTS = ("未詳", "不詳", "某", "氏(", "妻)", "妃)", "母)", "女)", "子)", "繼室")


def chinese_number(number: int) -> str:
    if number <= 10:
        return "十" if number == 10 else CHINESE_NUMBERS[number]
    if number < 20:
        return "十" + CHINESE_NUMBERS[number % 10]
    if number < 100:
        ten, one = divmod(number, 10)
        return CHINESE_NUMBERS[ten] + "十" + (CHINESE_NUMBERS[one] if one else "")
    if number == 100:
        return "一百"
    if number < 110:
        return "一百零" + CHINESE_NUMBERS[number - 100]
    ten_part = number - 100
    return "一百" + chinese_number(ten_part)


def clean_name(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def usable_name(value: Any, min_len: int = 2, max_len: int = 6) -> bool:
    name = clean_name(value)
    if not (min_len <= len(name) <= max_len):
        return False
    if any(part in name for part in FORBIDDEN_NAME_PARTS):
        return False
    return not re.search(r"[A-Za-z0-9\[\]()/（）？?;；,，]", name)


def unique_by_name(rows: list[dict[str, Any]], name_key: str, limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        name = clean_name(row.get(name_key))
        if name and name not in seen:
            seen.add(name)
            result.append(row)
        if len(result) >= limit:
            break
    return result


def fetch_entities(db_path: Path) -> dict[str, list[dict[str, Any]]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    dynasty = {
        row["c_dy"]: row["c_dynasty_chn"]
        for row in conn.execute("SELECT c_dy, c_dynasty_chn FROM DYNASTIES")
    }

    persons = [
        dict(row)
        for row in conn.execute(
            """
            SELECT c_personid, c_name_chn, c_index_year, c_birthyear, c_deathyear, c_dy
            FROM BIOG_MAIN
            WHERE c_personid > 0
              AND c_name_chn IS NOT NULL
              AND c_index_year IS NOT NULL
              AND length(c_name_chn) BETWEEN 2 AND 3
            ORDER BY (c_personid * 37) % 9973, c_personid
            LIMIT 1200
            """
        )
        if usable_name(row["c_name_chn"], 2, 3)
    ]
    persons = unique_by_name(persons, "c_name_chn", 30)
    for row in persons:
        row["dynasty"] = dynasty.get(row.get("c_dy"))

    places = [
        dict(row)
        for row in conn.execute(
            """
            SELECT c_addr_id, c_name_chn, x_coord, y_coord
            FROM ADDR_CODES
            WHERE c_addr_id > 0
              AND c_name_chn IS NOT NULL
              AND x_coord IS NOT NULL
              AND y_coord IS NOT NULL
              AND x_coord != 0
              AND y_coord != 0
              AND length(c_name_chn) BETWEEN 2 AND 5
            ORDER BY (c_addr_id * 53) % 10007, c_addr_id
            LIMIT 1600
            """
        )
        if usable_name(row["c_name_chn"], 2, 5)
        and not any(suffix in row["c_name_chn"] for suffix in ("轄區", "省市", "地區"))
    ]
    places = unique_by_name(places, "c_name_chn", 34)

    offices = [
        dict(row)
        for row in conn.execute(
            """
            SELECT c_office_id, c_office_chn, c_office_pinyin, c_office_trans
            FROM OFFICE_CODES
            WHERE c_office_id > 0
              AND c_office_chn IS NOT NULL
              AND length(c_office_chn) BETWEEN 2 AND 6
            ORDER BY (c_office_id * 41) % 8191, c_office_id
            LIMIT 1000
            """
        )
        if usable_name(row["c_office_chn"], 2, 6)
    ]
    offices = unique_by_name(offices, "c_office_chn", 20)

    reigns = [
        dict(row)
        for row in conn.execute(
            """
            SELECT c_nianhao_id, c_nianhao_chn, c_nianhao_pin, c_dy, c_dynasty_chn
            FROM NIAN_HAO
            WHERE c_nianhao_id > 0
              AND c_nianhao_chn IS NOT NULL
              AND length(c_nianhao_chn) BETWEEN 2 AND 4
            ORDER BY (c_nianhao_id * 29) % 4099, c_nianhao_id
            LIMIT 600
            """
        )
        if usable_name(row["c_nianhao_chn"], 2, 4)
    ]
    reigns = unique_by_name(reigns, "c_nianhao_chn", 16)
    conn.close()
    return {"person": persons, "place": places, "office": offices, "reign": reigns}


def build_authority(entities: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    authority: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in entities}

    def add(entity_text: str, entity_type: str, source_id: Any, extra: dict[str, Any]) -> dict[str, Any]:
        item = {
            "authority_id": f"auth_{len(authority) + 1:06d}",
            "entity_text": entity_text,
            "entity_type": entity_type,
            "canonical_name": entity_text,
            "source": "CBDB",
            "source_id": str(source_id),
            "note": "合成示範文本使用；實體資料取自 CBDB SQLite，供 MCP 標註流程展示",
        }
        item.update({key: value for key, value in extra.items() if value not in (None, "")})
        authority.append(item)
        grouped[entity_type].append(item)
        return item

    for row in entities["person"]:
        person_id = row["c_personid"]
        add(
            clean_name(row["c_name_chn"]),
            "person",
            person_id,
            {
                "source_url": PERSON_URL.format(person_id=person_id),
                "index_year": row.get("c_index_year"),
                "birth_year": row.get("c_birthyear") or None,
                "death_year": row.get("c_deathyear") or None,
                "dynasty": row.get("dynasty"),
            },
        )
    for row in entities["place"]:
        add(
            clean_name(row["c_name_chn"]),
            "place",
            row["c_addr_id"],
            {"x_coord": row.get("x_coord"), "y_coord": row.get("y_coord")},
        )
    for row in entities["office"]:
        add(
            clean_name(row["c_office_chn"]),
            "office",
            row["c_office_id"],
            {
                "office_pinyin": row.get("c_office_pinyin"),
                "office_translation": row.get("c_office_trans"),
            },
        )
    for row in entities["reign"]:
        add(
            clean_name(row["c_nianhao_chn"]),
            "reign",
            row["c_nianhao_id"],
            {"dynasty": row.get("c_dynasty_chn")},
        )
    return authority, grouped


def pick(items: list[dict[str, Any]], index: int) -> dict[str, Any]:
    return items[index % len(items)]


def entity_name(grouped: dict[str, list[dict[str, Any]]], entity_type: str, index: int) -> str:
    return pick(grouped[entity_type], index)["entity_text"]


def generate_text(grouped: dict[str, list[dict[str, Any]]]) -> str:
    random.seed(RANDOM_SEED)
    chapter_lines: list[str] = []
    verbs = ["校籍", "問道", "議禮", "修牒", "按圖", "考碑", "錄事", "訪古", "辨年", "會議"]
    textures = ["雨後", "燈下", "驛中", "水次", "城東", "山門", "廨舍", "書院", "江亭", "官署"]
    endings = ["其事散見舊牘，今但存其梗概。", "眾人各記一條，以備後來覆按。", "此段本為示範假文，不據原書敘事。", "卷中名號皆取權威表，以便展示標註。"]

    for chapter in range(1, 121):
        p1 = entity_name(grouped, "person", chapter * 3)
        p2 = entity_name(grouped, "person", chapter * 3 + 1)
        place = entity_name(grouped, "place", chapter * 5)
        office = entity_name(grouped, "office", chapter * 2)
        reign = entity_name(grouped, "reign", chapter)
        title = f"第{chinese_number(chapter)}回　{p1}{random.choice(verbs)}{place}　{p2}{office}記{reign}"
        chapter_lines.append(title)

        paragraph_count = 5 + (chapter % 4)
        for paragraph in range(paragraph_count):
            idx = chapter * 17 + paragraph * 7
            a = entity_name(grouped, "person", idx)
            b = entity_name(grouped, "person", idx + 1)
            x = entity_name(grouped, "place", idx)
            y = entity_name(grouped, "place", idx + 1)
            off1 = entity_name(grouped, "office", idx)
            era = entity_name(grouped, "reign", idx)
            texture = random.choice(textures)
            ending = random.choice(endings)
            if paragraph % 4 == 0:
                body = f"{texture}，{a}以{off1}至{x}，見{b}自{y}來，因問{era}以後圖籍。旁錄山川，書為短牒。{ending}"
            elif paragraph % 4 == 1:
                body = f"{a}與{b}同署{off1}，又持牒赴{x}。其牒先稱{era}，後及{y}，文句錯落，皆為展示之假文。"
            elif paragraph % 4 == 2:
                body = f"或曰{x}近{y}，或曰山川當道。{a}據碑記，{b}據官牒，兩說互異，乃請吏員覆校。"
            else:
                body = f"{era}之歲，{off1}議於{x}。{a}、{b}各持一冊，先列人名，次列地名，以明 CBDB 權威資料可互相參照。"
            chapter_lines.append(f"　　{body}")
    return "\n".join(chapter_lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic CBDB-heavy demo corpus.")
    parser.add_argument("--db", default=str(DB_PATH), help="CBDB SQLite path")
    parser.add_argument("--input-output", default=str(INPUT_PATH), help="Output path for synthetic sample text")
    parser.add_argument("--authority-output", default=str(AUTHORITY_PATH), help="Output path for authority table")
    args = parser.parse_args()

    entities = fetch_entities(Path(args.db))
    authority, grouped = build_authority(entities)
    text = generate_text(grouped)

    input_path = Path(args.input_output)
    auth_path = Path(args.authority_output)
    input_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(text, encoding="utf-8")
    auth_path.write_text(json.dumps(authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {input_path}: 120 chapters")
    print(f"wrote {auth_path}: {len(authority)} CBDB authority records")
    print(
        "entity counts:",
        ", ".join(f"{key}={len(value)}" for key, value in grouped.items()),
    )


if __name__ == "__main__":
    main()
