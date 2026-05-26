from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path("config/workflow.json")
CHAPTER_PATTERNS = [
    re.compile(r"^第[一二三四五六七八九十百千零〇兩\d\s　]+[章回].*$"),
    re.compile(r"^卷[一二三四五六七八九十百千零〇兩\d上中下\s　]*.*$"),
    re.compile(r"^#{1,6}\s+.+$"),
]


@dataclass
class WorkflowConfig:
    input_text: Path
    output_dir: Path
    authority_table: Path
    html_output: Path
    page_title: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Split text and export a CBDB-authority annotated HTML file.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Workflow config JSON path.")
    parser.add_argument("--input", help="Override input_text in config.")
    args = parser.parse_args()

    config = load_config(Path(args.config), args.input)
    text = config.input_text.read_text(encoding="utf-8")
    chapters, paragraphs = split_text(text)
    authority_table = read_json(config.authority_table, [])

    config.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(config.output_dir / "chapters.json", chapters)
    write_json(config.output_dir / "paragraphs.json", paragraphs)
    if not config.authority_table.exists():
        write_json(config.authority_table, [])
    write_html(config.html_output, config.page_title, chapters, paragraphs, authority_table)

    print(f"Wrote {config.output_dir / 'chapters.json'}")
    print(f"Wrote {config.output_dir / 'paragraphs.json'}")
    print(f"Wrote {config.authority_table}")
    print(f"Wrote {config.html_output}")


def load_config(path: Path, input_override: str | None = None) -> WorkflowConfig:
    raw = read_json(path, {})
    input_text = Path(input_override or raw.get("input_text", "data/input/sample-1.txt"))
    output_dir = Path(raw.get("output_dir", "data/output"))
    authority_table = Path(raw.get("authority_table", output_dir / "authority_table.json"))
    html_output = Path(raw.get("html_output", output_dir / "annotated.html"))
    return WorkflowConfig(
        input_text=input_text,
        output_dir=output_dir,
        authority_table=authority_table,
        html_output=html_output,
        page_title=raw.get("page_title", "CBDB MCP Annotation Demo"),
    )


def split_text(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chapters: list[dict[str, Any]] = []
    paragraphs: list[dict[str, Any]] = []
    current_chapter: dict[str, Any] | None = None
    buffer: list[str] = []

    def ensure_chapter(title: str = "未分章") -> dict[str, Any]:
        nonlocal current_chapter
        if current_chapter is None:
            current_chapter = {"chapter_id": f"ch_{len(chapters) + 1:04d}", "title": title}
            chapters.append(current_chapter)
        return current_chapter

    def flush() -> None:
        if not buffer:
            return
        chapter = ensure_chapter()
        text_value = "\n".join(line for line in buffer if line.strip()).strip()
        buffer.clear()
        if not text_value:
            return
        paragraphs.append(
            {
                "paragraph_id": f"p_{len(paragraphs) + 1:06d}",
                "chapter_id": chapter["chapter_id"],
                "text": text_value,
            }
        )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if is_chapter_heading(line):
            flush()
            current_chapter = {"chapter_id": f"ch_{len(chapters) + 1:04d}", "title": clean_heading(line)}
            chapters.append(current_chapter)
            continue
        ensure_chapter()
        buffer.append(raw_line.strip("\ufeff"))
    flush()
    return chapters, paragraphs


def is_chapter_heading(line: str) -> bool:
    return any(pattern.match(line) for pattern in CHAPTER_PATTERNS)


def clean_heading(line: str) -> str:
    return re.sub(r"^#{1,6}\s+", "", line).strip()


def annotate_text(text: str, authority_table: list[dict[str, Any]]) -> str:
    candidates = sorted(
        [item for item in authority_table if item.get("entity_text")],
        key=lambda item: len(str(item["entity_text"])),
        reverse=True,
    )
    pieces: list[str] = []
    index = 0
    while index < len(text):
        match = next((item for item in candidates if text.startswith(str(item["entity_text"]), index)), None)
        if match is None:
            pieces.append(html.escape(text[index]))
            index += 1
            continue
        entity_text = str(match["entity_text"])
        pieces.append(render_entity_span(entity_text, match))
        index += len(entity_text)
    return "".join(pieces)


def render_entity_span(entity_text: str, item: dict[str, Any]) -> str:
    entity_type = html.escape(str(item.get("entity_type", "entity")))
    authority_id = html.escape(str(item.get("authority_id", "")))
    source = html.escape(str(item.get("source", "CBDB")))
    source_id = html.escape(str(item.get("source_id", "")))
    canonical = html.escape(str(item.get("canonical_name") or entity_text))
    title = f"{canonical} / {source}:{source_id}".strip()
    return (
        f'<span class="entity {entity_type}" data-authority-id="{authority_id}" '
        f'data-source="{source}" data-source-id="{source_id}" title="{html.escape(title)}">'
        f"{html.escape(entity_text)}</span>"
    )


def write_html(
    output_path: Path,
    page_title: str,
    chapters: list[dict[str, Any]],
    paragraphs: list[dict[str, Any]],
    authority_table: list[dict[str, Any]],
) -> None:
    by_chapter: dict[str, list[dict[str, Any]]] = {chapter["chapter_id"]: [] for chapter in chapters}
    for paragraph in paragraphs:
        by_chapter.setdefault(paragraph["chapter_id"], []).append(paragraph)

    authority_json = json.dumps(authority_table, ensure_ascii=False)
    body = [
        "<!doctype html>",
        '<html lang="zh-Hant">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(page_title)}</title>",
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">',
        "<style>",
        CSS,
        "</style>",
        "</head>",
        "<body>",
        "<header>",
        '<button id="toggleLeft" class="panel-toggle" type="button" title="展開/收合章節" aria-label="展開/收合章節" aria-expanded="true"></button>',
        f'<div><h1>《水滸傳》<span class="subtitle">{html.escape(page_title)}</span></h1></div>',
        '<div class="type-badges" aria-label="實體類型">',
        '<button class="type-badge" type="button" data-type="person"><span class="swatch person"></span>人物 <strong data-type-count="person">0</strong></button>',
        '<button class="type-badge" type="button" data-type="place"><span class="swatch place"></span>地點 <strong data-type-count="place">0</strong></button>',
        '<button class="type-badge" type="button" data-type="office"><span class="swatch office"></span>職官 <strong data-type-count="office">0</strong></button>',
        '<button class="type-badge" type="button" data-type="reign"><span class="swatch reign"></span>年號 <strong data-type-count="reign">0</strong></button>',
        "</div>",
        '<button id="toggleRight" class="panel-toggle" type="button" title="展開/收合標註資訊" aria-label="展開/收合標註資訊" aria-expanded="true"></button>',
        "</header>",
        '<div class="layout">',
        '<aside class="chapters"><div class="panel-head"><h2>章節</h2>'
        f'<span class="meta">{len(chapters)} 回</span></div><ol class="chapter-list">',
    ]
    for chapter in chapters:
        body.append(
            f'<li><a class="chapter-link" href="#{html.escape(chapter["chapter_id"])}" '
            f'data-chapter-link="{html.escape(chapter["chapter_id"])}">'
            f'<span class="chapter-title">{html.escape(chapter["title"])}</span></a></li>'
        )
    body.extend(["</ol></aside>", '<main><div class="reader">'])
    for chapter in chapters:
        body.append(f'<article id="{html.escape(chapter["chapter_id"])}">')
        body.append(f'<h2>{html.escape(chapter["title"])}</h2>')
        for paragraph_index, paragraph in enumerate(by_chapter.get(chapter["chapter_id"], []), start=1):
            annotated = annotate_text(paragraph["text"], authority_table)
            body.append(
                f'<p id="{html.escape(paragraph["paragraph_id"])}" data-paragraph="{paragraph_index}">'
                f"{annotated}</p>"
            )
        body.append("</article>")
    body.extend(
        [
            "</div></main>",
            '<aside class="inspector">',
            '<div class="panel-head"><h2>詞頻統計</h2><span class="meta">CBDB authority</span></div>',
            '<div class="stat-grid">',
            '<div class="stat"><strong id="totalEntities">0</strong><span>實體權威筆數</span></div>',
            '<div class="stat"><strong id="totalMentions">0</strong><span>標註出現次數</span></div>',
            "</div>",
            '<section class="section" id="detailSection">',
            "<h3>CBDB 標註內容</h3>",
            '<div id="detail" class="empty">點選正文中的高亮實體，右側會顯示 CBDB canonical name、ID、朝代、年份、職官譯名或 GIS 座標。</div>',
            "</section>",
            '<section class="section" id="mapSection" hidden>',
            "<h3>GIS Map</h3>",
            '<div id="map"></div>',
            '<div id="mapMessage" class="map-message" hidden></div>',
            "</section>",
            '<section class="section"><h3>實體詞頻</h3><ul class="freq-list" id="frequencyList">',
        ]
    )
    body.extend(
        [
            "</ul></section></aside></div>",
            f'<footer>本頁面為示範網頁，內容經過亂數處理。實體判讀由 Codex 輔助完成，權威資料來源為 <a href="https://projects.iq.harvard.edu/cbdb" target="_blank" rel="noreferrer">China Biographical Database (CBDB)</a>, Harvard University, Academia Sinica, and Peking University（共 {len(authority_table)} 筆實體）。</footer>',
            '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>',
            "<script>",
            f"const AUTHORITY = {authority_json};",
            JS,
            "</script>",
            "</body></html>",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(body), encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


CSS = """
:root {
  color-scheme: light;
  --ink: #1f2933;
  --muted: #657080;
  --line: #d8dee8;
  --panel: #fff;
  --bg: #f7f8fa;
  --accent: #9f2d20;
  --person: #fff0b8;
  --person-line: #d49a00;
  --place: #dff3e6;
  --place-line: #2f8c56;
  --office: #d9e9ff;
  --office-line: #2b6fb8;
  --reign: #ffe0cc;
  --reign-line: #c46227;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  padding-bottom: 46px;
  color: var(--ink);
  background: var(--bg);
  font-family: -apple-system, BlinkMacSystemFont, "Noto Sans TC", "PingFang TC", sans-serif;
}
header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: grid;
  grid-template-columns: 34px minmax(230px, auto) minmax(0, 1fr) 34px;
  align-items: center;
  gap: 16px;
  min-height: 58px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, .96);
  backdrop-filter: blur(10px);
}
.panel-toggle {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  padding: 0;
}
.panel-toggle svg { width: 23px; height: 23px; display: block; }
h1 { margin: 0; font-size: 19px; line-height: 1.25; white-space: nowrap; }
.subtitle { display: block; margin-top: 2px; color: var(--muted); font-size: 12px; font-weight: 400; }
.type-badges { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
.type-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  color: #263241;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}
.type-badge.is-off { opacity: .38; }
.swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; border: 1px solid currentColor; }
.swatch.person { background: var(--person); color: var(--person-line); }
.swatch.place { background: var(--place); color: var(--place-line); }
.swatch.office { background: var(--office); color: var(--office-line); }
.swatch.reign { background: var(--reign); color: var(--reign-line); }
.layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 360px;
  min-height: calc(100vh - 58px);
  transition: grid-template-columns .22s ease;
}
body.left-collapsed .layout { grid-template-columns: 0 minmax(0, 1fr) 360px; }
body.right-collapsed .layout { grid-template-columns: 280px minmax(0, 1fr) 0; }
body.left-collapsed.right-collapsed .layout { grid-template-columns: 0 minmax(0, 1fr) 0; }
.chapters, .inspector {
  position: sticky;
  top: 58px;
  height: calc(100vh - 58px);
  overflow: auto;
  background: var(--panel);
  transition: padding .22s ease, opacity .18s ease;
}
body.left-collapsed .chapters,
body.right-collapsed .inspector {
  padding: 0;
  border: 0;
  overflow: hidden;
  opacity: 0;
}
body.left-collapsed .chapters > *,
body.right-collapsed .inspector > * { display: none; }
.chapters { border-right: 1px solid var(--line); padding: 12px; }
.inspector { border-left: 1px solid var(--line); padding: 14px; }
.panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
.panel-head h2 { margin: 0; font-size: 15px; }
.meta { color: var(--muted); font-size: 12px; line-height: 1.55; }
.chapter-list { display: grid; gap: 2px; margin: 0; padding: 0; list-style: none; }
.chapter-link {
  display: block;
  padding: 6px 7px;
  border-radius: 6px;
  color: inherit;
  text-decoration: none;
  font-size: 13px;
  line-height: 1.4;
}
.chapter-link:hover, .chapter-link.active { background: #f1f4f8; }
.chapter-title { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
main { min-width: 0; padding: 28px 34px 56px; background: #fff; }
.reader {
  max-width: 980px;
  margin: 0 auto;
  font-family: "Noto Serif TC", "Songti TC", "PingFang TC", serif;
  font-size: 18px;
  line-height: 1.95;
}
article { scroll-margin-top: 76px; margin-bottom: 42px; }
article h2 { margin: 0 0 18px; padding-bottom: 9px; border-bottom: 1px solid var(--line); font-size: 28px; line-height: 1.35; }
p { margin: 0 0 1em; text-indent: 2em; white-space: pre-wrap; }
p::before {
  content: "#" attr(data-paragraph);
  display: inline-block;
  min-width: 58px;
  margin-left: -58px;
  padding-right: 8px;
  color: #8a94a3;
  font: 12px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  text-indent: 0;
  text-align: right;
  vertical-align: top;
}
.entity { padding: 0 .12em; border-radius: 3px; cursor: pointer; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
.entity.person { background: var(--person); }
.entity.place { background: var(--place); }
.entity.office { background: var(--office); }
.entity.reign { background: var(--reign); }
.entity.is-selected { outline: 2px solid #111827; outline-offset: 1px; }
body.hide-person .entity.person,
body.hide-place .entity.place,
body.hide-office .entity.office,
body.hide-reign .entity.reign { background: transparent; color: inherit; }
.stat-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 0 0 16px; }
.stat { padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: #fbfcfe; }
.stat strong { display: block; font-size: 22px; line-height: 1.1; font-variant-numeric: tabular-nums; }
.stat span { display: block; margin-top: 4px; color: var(--muted); font-size: 12px; }
.section { margin: 0 0 18px; padding-top: 14px; border-top: 1px solid var(--line); }
.section h3 { margin: 0 0 10px; font-size: 15px; }
.freq-list { display: grid; gap: 7px; margin: 0; padding: 0; list-style: none; }
.freq-btn {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 8px;
  border: 1px solid #e3e8ef;
  border-radius: 7px;
  background: #fff;
  color: inherit;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  text-align: left;
}
.freq-btn:hover { border-color: #b8c3d2; }
.freq-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.freq-count { color: var(--muted); font-variant-numeric: tabular-nums; }
.detail-title { margin: 0 0 4px; font-size: 20px; line-height: 1.3; }
.detail-subtitle { margin-bottom: 12px; color: var(--muted); font-size: 13px; }
.detail-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.detail-table th, .detail-table td { border-bottom: 1px solid #e8edf3; padding: 7px 0; vertical-align: top; text-align: left; }
.detail-table th { width: 96px; color: var(--muted); font-weight: 500; padding-right: 10px; }
.detail-table a { color: var(--accent); }
#map { width: 100%; height: 240px; margin-top: 12px; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #eef2f6; }
#map.leaflet-container { font-family: -apple-system, BlinkMacSystemFont, "Noto Sans TC", "PingFang TC", sans-serif; }
.map-message { margin-top: 10px; padding: 10px; border: 1px dashed #c9d2df; border-radius: 8px; color: var(--muted); background: #fbfcfe; font-size: 13px; line-height: 1.55; }
.empty { padding: 12px; border: 1px dashed #c9d2df; border-radius: 8px; color: var(--muted); background: #fbfcfe; font-size: 13px; line-height: 1.65; }
footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  padding: 14px 18px;
  border-top: 1px solid var(--line);
  background: rgba(255, 255, 255, .96);
  backdrop-filter: blur(10px);
  color: var(--muted);
  font-size: 13px;
  text-align: center;
}
@media (max-width: 1120px) {
  .layout { grid-template-columns: 220px minmax(0, 1fr); }
  body.left-collapsed .layout,
  body.right-collapsed .layout,
  body.left-collapsed.right-collapsed .layout { grid-template-columns: 0 minmax(0, 1fr); }
  .inspector { grid-column: 1 / -1; position: static; height: auto; border-left: 0; border-top: 1px solid var(--line); }
}
@media (max-width: 760px) {
  header { grid-template-columns: 34px 1fr 34px; align-items: start; }
  header > div:first-of-type { grid-column: 2; grid-row: 1; }
  #toggleLeft { grid-column: 1; grid-row: 1; }
  #toggleRight { grid-column: 3; grid-row: 1; }
  .type-badges { grid-column: 1 / -1; justify-content: flex-start; }
  .layout { display: block; }
  .chapters, .inspector { position: static; height: auto; border: 0; border-bottom: 1px solid var(--line); }
  .chapter-list { max-height: 220px; overflow: auto; }
  main { padding: 22px 18px 42px; }
  .reader { font-size: 17px; }
  p::before { display: none; }
}
"""


JS = """
const authorityById = new Map(AUTHORITY.map(item => [item.authority_id, item]));
let map = null;
let marker = null;
let activeMapPoint = null;
const icons = {
  leftExpand: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6z"/><path d="M9 4v16"/><path d="M14 10l2 2-2 2"/></svg>',
  leftCollapse: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6z"/><path d="M9 4v16"/><path d="M15 10l-2 2 2 2"/></svg>',
  rightExpand: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6z"/><path d="M15 4v16"/><path d="M10 10l-2 2 2 2"/></svg>',
  rightCollapse: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6z"/><path d="M15 4v16"/><path d="M9 10l2 2-2 2"/></svg>'
};

const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

function countMentions() {
  const counts = new Map();
  document.querySelectorAll('.entity[data-authority-id]').forEach(node => {
    const id = node.dataset.authorityId;
    counts.set(id, (counts.get(id) || 0) + 1);
  });
  return counts;
}

function initStats(counts) {
  const typeCounts = {person: 0, place: 0, office: 0, reign: 0};
  let totalMentions = 0;
  AUTHORITY.forEach(item => {
    const count = counts.get(item.authority_id) || 0;
    totalMentions += count;
    if (item.entity_type in typeCounts) typeCounts[item.entity_type] += count;
  });
  document.getElementById('totalEntities').textContent = AUTHORITY.length;
  document.getElementById('totalMentions').textContent = totalMentions;
  Object.entries(typeCounts).forEach(([type, count]) => {
    const target = document.querySelector(`[data-type-count="${type}"]`);
    if (target) target.textContent = count;
  });
}

function initFrequencyList(counts) {
  const list = document.getElementById('frequencyList');
  const rows = AUTHORITY
    .map(item => ({...item, count: counts.get(item.authority_id) || 0}))
    .filter(item => item.count > 0)
    .sort((a, b) => b.count - a.count || String(a.entity_text || '').localeCompare(String(b.entity_text || ''), 'zh-Hant'));
  list.innerHTML = rows.map(item => {
    const name = item.canonical_name && item.canonical_name !== item.entity_text
      ? `${item.entity_text} → ${item.canonical_name}`
      : item.entity_text;
    return `
      <li>
        <button class="freq-btn" type="button" data-authority-id="${esc(item.authority_id)}">
          <span class="freq-name">${esc(name)}</span>
          <span class="freq-count">${item.count}</span>
        </button>
      </li>
    `;
  }).join('');
  list.querySelectorAll('[data-authority-id]').forEach(btn => {
    btn.addEventListener('click', () => selectAuthority(btn.dataset.authorityId, true));
  });
}

function initEntityClicks() {
  document.querySelectorAll('.entity[data-authority-id]').forEach(node => {
    node.addEventListener('click', event => {
      event.stopPropagation();
      selectAuthority(node.dataset.authorityId, false, node);
    });
  });
}

function selectAuthority(authorityId, scrollToFirst = false, sourceNode = null) {
  const item = authorityById.get(authorityId);
  if (!item) return;
  expandRightPanel();
  document.querySelectorAll('.entity.is-selected').forEach(node => node.classList.remove('is-selected'));
  const matches = document.querySelectorAll(`.entity[data-authority-id="${CSS.escape(authorityId)}"]`);
  matches.forEach(node => node.classList.add('is-selected'));
  if (scrollToFirst && matches[0]) {
    matches[0].scrollIntoView({block: 'center'});
  } else if (sourceNode) {
    sourceNode.classList.add('is-selected');
  }
  renderDetail(item, matches.length);
}

function expandRightPanel() {
  if (!document.body.classList.contains('right-collapsed')) return;
  document.body.classList.remove('right-collapsed');
  updatePanelToggleIcons();
  if (map) setTimeout(() => map.invalidateSize(), 240);
}

function renderDetail(item, count) {
  const rows = [
    ['原文', item.entity_text],
    ['類型', typeLabel(item.entity_type)],
    ['CBDB 名稱', item.canonical_name],
    ['CBDB ID', item.source_id],
    ['出現次數', count],
    ['朝代', item.dynasty],
    ['Index year', item.index_year],
    ['生卒', formatLife(item)],
    ['職官拼音', item.office_pinyin],
    ['職官譯名', item.office_translation],
    ['座標', formatCoords(item)],
    ['說明', item.note],
  ].filter(([, value]) => value !== undefined && value !== null && value !== '');
  const sourceUrl = item.source_url
    ? `<tr><th>參考來源</th><td><a href="${esc(item.source_url)}" target="_blank" rel="noreferrer">開啟 CBDB</a></td></tr>`
    : '';
  const heading = esc(item.canonical_name || item.entity_text);
  document.getElementById('detail').className = '';
  document.getElementById('detail').innerHTML = `
    <h4 class="detail-title">${heading}</h4>
    <div class="detail-subtitle">${esc(item.source || 'CBDB')}:${esc(item.source_id || '')} / ${esc(item.authority_id)}</div>
    <table class="detail-table">
      ${rows.map(([label, value]) => `<tr><th>${esc(label)}</th><td>${esc(value)}</td></tr>`).join('')}
      ${sourceUrl}
    </table>
  `;
  renderMap(item);
}

function typeLabel(type) {
  return {person: '人物', place: '地點', office: '職官', reign: '年號'}[type] || type;
}

function formatLife(item) {
  if (!item.birth_year && !item.death_year) return '';
  return `${item.birth_year || '?'}-${item.death_year || '?'}`;
}

function formatCoords(item) {
  const x = Number(item.x_coord);
  const y = Number(item.y_coord);
  if (!Number.isFinite(x) || !Number.isFinite(y) || (x === 0 && y === 0)) return '';
  return `${y}, ${x}`;
}

function renderMap(item) {
  const section = document.getElementById('mapSection');
  const message = document.getElementById('mapMessage');
  const mapEl = document.getElementById('map');
  const x = Number(item.x_coord);
  const y = Number(item.y_coord);
  if (!Number.isFinite(x) || !Number.isFinite(y) || (x === 0 && y === 0)) {
    if (item.entity_type === 'place') {
      section.hidden = false;
      mapEl.hidden = true;
      message.hidden = false;
      message.textContent = '此 CBDB 地名記錄未提供可用 GIS 座標，因此不顯示地圖。';
    } else {
      section.hidden = true;
    }
    return;
  }
  section.hidden = false;
  mapEl.hidden = false;
  message.hidden = true;
  activeMapPoint = {lat: y, lng: x, label: item.canonical_name, sourceId: item.source_id || ''};
  setTimeout(() => {
    if (!window.L) {
      message.hidden = false;
      message.textContent = 'Leaflet 尚未載入。若以本機檔案開啟，請確認瀏覽器可連線到 Leaflet CDN 與 OpenStreetMap tile server。';
      return;
    }
    if (!map) {
      map = L.map('map', {scrollWheelZoom: false});
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);
    }
    map.setView([y, x], 8, {animate: true});
    if (marker) marker.remove();
    marker = L.marker([y, x]).addTo(map).bindPopup(`${esc(item.canonical_name)}<br>CBDB:${esc(item.source_id || '')}`);
    marker.openPopup();
    refreshMapView();
    setTimeout(refreshMapView, 260);
  }, 80);
}

function refreshMapView() {
  if (!map || !activeMapPoint) return;
  const point = [activeMapPoint.lat, activeMapPoint.lng];
  map.invalidateSize({pan: false});
  map.setView(point, map.getZoom() || 8, {animate: false});
  if (marker) marker.openPopup();
}

function initTypeBadges() {
  document.querySelectorAll('.type-badge[data-type]').forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.dataset.type;
      btn.classList.toggle('is-off');
      document.body.classList.toggle(`hide-${type}`, btn.classList.contains('is-off'));
    });
  });
}

function initChapterSpy() {
  const links = new Map([...document.querySelectorAll('[data-chapter-link]')].map(link => [link.dataset.chapterLink, link]));
  const observer = new IntersectionObserver(entries => {
    const visible = entries
      .filter(entry => entry.isIntersecting)
      .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
    if (!visible) return;
    links.forEach(link => link.classList.remove('active'));
    const link = links.get(visible.target.id);
    if (link) link.classList.add('active');
  }, {rootMargin: '-80px 0px -72% 0px', threshold: 0.01});
  document.querySelectorAll('article[id]').forEach(article => observer.observe(article));
}

function initPanelToggles() {
  const left = document.getElementById('toggleLeft');
  const right = document.getElementById('toggleRight');
  left.addEventListener('click', () => {
    document.body.classList.toggle('left-collapsed');
    updatePanelToggleIcons();
  });
  right.addEventListener('click', () => {
    document.body.classList.toggle('right-collapsed');
    updatePanelToggleIcons();
    if (!document.body.classList.contains('right-collapsed') && map) {
      setTimeout(refreshMapView, 240);
    }
  });
  updatePanelToggleIcons();
}

function updatePanelToggleIcons() {
  const left = document.getElementById('toggleLeft');
  const right = document.getElementById('toggleRight');
  if (!left || !right) return;
  const leftCollapsed = document.body.classList.contains('left-collapsed');
  const rightCollapsed = document.body.classList.contains('right-collapsed');
  left.innerHTML = leftCollapsed ? icons.leftExpand : icons.leftCollapse;
  right.innerHTML = rightCollapsed ? icons.rightExpand : icons.rightCollapse;
  left.setAttribute('aria-expanded', String(!leftCollapsed));
  right.setAttribute('aria-expanded', String(!rightCollapsed));
}

const counts = countMentions();
initStats(counts);
initFrequencyList(counts);
initEntityClicks();
initTypeBadges();
initChapterSpy();
initPanelToggles();
"""


if __name__ == "__main__":
    main()
