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
        f"<h1>{html.escape(page_title)}</h1>",
        '<div class="badges"><span>人物</span><span>地名</span><span>職官</span><span>年號</span></div>',
        "</header>",
        '<div class="layout">',
        '<aside class="chapters"><h2>章節</h2><ol>',
    ]
    for idx, chapter in enumerate(chapters, start=1):
        body.append(
            f'<li><a href="#{html.escape(chapter["chapter_id"])}">'
            f'{idx:03d} {html.escape(chapter["title"])}</a></li>'
        )
    body.extend(["</ol></aside>", "<main>"])
    for chapter in chapters:
        body.append(f'<article id="{html.escape(chapter["chapter_id"])}">')
        body.append(f'<h2>{html.escape(chapter["title"])}</h2>')
        for paragraph in by_chapter.get(chapter["chapter_id"], []):
            annotated = annotate_text(paragraph["text"], authority_table)
            body.append(f'<p id="{html.escape(paragraph["paragraph_id"])}">{annotated}</p>')
        body.append("</article>")
    body.extend(
        [
            "</main>",
            '<aside class="inspector"><h2>CBDB 標註內容</h2>',
            '<div id="detail" class="empty">點選高亮實體後，這裡會顯示 CBDB 權威資料。</div>',
            '<div id="map" hidden></div>',
            "<h2>Authority List</h2>",
            '<div class="authority-list">',
        ]
    )
    for item in authority_table:
        label = item.get("canonical_name") or item.get("entity_text") or item.get("source_id")
        body.append(
            f'<button type="button" class="authority-btn" data-authority-id="{html.escape(str(item.get("authority_id", "")))}">'
            f'{html.escape(str(label))}</button>'
        )
    body.extend(
        [
            "</div></aside></div>",
            f"<footer>本頁面為示範網頁。標註來源為 ChatGPT + CBDB 資料庫( 共{len(authority_table)} 筆實體)</footer>",
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
:root { --line:#d8dee8; --muted:#657080; --bg:#f7f8fa; --panel:#fff; --ink:#1f2933; }
* { box-sizing: border-box; }
body { margin: 0; padding-bottom: 44px; color: var(--ink); background: var(--bg); font-family: -apple-system, BlinkMacSystemFont, "Noto Sans TC", "PingFang TC", sans-serif; }
header { position: sticky; top: 0; z-index: 10; display:flex; align-items:center; justify-content:space-between; gap:16px; min-height:58px; padding:12px 18px; border-bottom:1px solid var(--line); background:rgba(255,255,255,.96); }
h1 { margin:0; font-size:20px; }
.badges { display:flex; gap:8px; flex-wrap:wrap; }
.badges span { border:1px solid var(--line); border-radius:999px; padding:5px 10px; background:#fff; font-size:13px; }
.layout { display:grid; grid-template-columns:280px minmax(0, 1fr) 340px; min-height:calc(100vh - 58px); }
.chapters, .inspector { position:sticky; top:58px; height:calc(100vh - 58px); overflow:auto; padding:16px; background:var(--panel); }
.chapters { border-right:1px solid var(--line); }
.inspector { border-left:1px solid var(--line); }
.chapters ol { display:grid; gap:5px; padding-left:20px; }
.chapters a { color:inherit; text-decoration:none; font-size:13px; }
main { min-width:0; padding:28px 34px 64px; background:#fff; }
article { max-width:920px; margin:0 auto 42px; }
article h2 { margin:0 0 18px; padding-bottom:9px; border-bottom:1px solid var(--line); font-size:26px; }
p { margin:0 0 1em; white-space:pre-wrap; text-indent:2em; font-family:"Noto Serif TC", "Songti TC", serif; font-size:18px; line-height:1.95; }
.entity { padding:0 .1em; border-bottom:2px solid transparent; border-radius:3px; cursor:pointer; }
.entity.person { background:#fff0b8; border-bottom-color:#d49a00; }
.entity.place { background:#dff3e6; border-bottom-color:#2f8c56; }
.entity.office { background:#d9e9ff; border-bottom-color:#2b6fb8; }
.entity.reign { background:#ffe0cc; border-bottom-color:#c46227; }
.entity.selected { outline:2px solid #111827; outline-offset:1px; }
.empty { padding:12px; border:1px dashed #c9d2df; border-radius:8px; color:var(--muted); line-height:1.6; }
.detail-table { width:100%; border-collapse:collapse; font-size:13px; }
.detail-table th, .detail-table td { border-bottom:1px solid #e8edf3; padding:7px 0; text-align:left; vertical-align:top; }
.detail-table th { width:92px; color:var(--muted); font-weight:500; padding-right:10px; }
#map { width:100%; height:240px; margin:14px 0; border:1px solid var(--line); border-radius:8px; }
.authority-list { display:grid; gap:7px; }
.authority-btn { min-height:32px; border:1px solid #e3e8ef; border-radius:7px; background:#fff; text-align:left; cursor:pointer; }
footer { position:fixed; left:0; right:0; bottom:0; z-index:20; padding:12px 16px; border-top:1px solid var(--line); background:rgba(255,255,255,.96); color:var(--muted); text-align:center; font-size:13px; }
@media (max-width: 980px) { .layout { display:block; } .chapters, .inspector { position:static; height:auto; border:0; border-bottom:1px solid var(--line); } main { padding:22px 18px 58px; } }
"""


JS = """
const byId = new Map(AUTHORITY.map(item => [item.authority_id, item]));
let map = null;
let marker = null;

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function selectAuthority(id) {
  const item = byId.get(id);
  if (!item) return;
  document.querySelectorAll('.entity.selected').forEach(node => node.classList.remove('selected'));
  document.querySelectorAll(`.entity[data-authority-id="${CSS.escape(id)}"]`).forEach(node => node.classList.add('selected'));
  const rows = [
    ['原文', item.entity_text],
    ['類型', item.entity_type],
    ['CBDB 名稱', item.canonical_name],
    ['CBDB ID', item.source_id],
    ['朝代', item.dynasty],
    ['Index year', item.index_year],
    ['生年', item.birth_year],
    ['卒年', item.death_year],
    ['職官拼音', item.office_pinyin],
    ['職官譯名', item.office_translation],
    ['座標', formatCoords(item)],
    ['說明', item.note]
  ].filter(([, value]) => value !== undefined && value !== null && value !== '');
  if (item.source_url) rows.push(['參考來源', `<a href="${esc(item.source_url)}" target="_blank" rel="noreferrer">開啟 CBDB</a>`]);
  document.getElementById('detail').className = '';
  document.getElementById('detail').innerHTML = `<table class="detail-table">${rows.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${k === '參考來源' ? v : esc(v)}</td></tr>`).join('')}</table>`;
  renderMap(item);
}

function formatCoords(item) {
  const x = Number(item.x_coord);
  const y = Number(item.y_coord);
  if (!Number.isFinite(x) || !Number.isFinite(y) || (x === 0 && y === 0)) return '';
  return `${y}, ${x}`;
}

function renderMap(item) {
  const mapEl = document.getElementById('map');
  const x = Number(item.x_coord);
  const y = Number(item.y_coord);
  if (!Number.isFinite(x) || !Number.isFinite(y) || (x === 0 && y === 0) || !window.L) {
    mapEl.hidden = true;
    return;
  }
  mapEl.hidden = false;
  setTimeout(() => {
    if (!map) {
      map = L.map('map');
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);
    }
    map.invalidateSize();
    map.setView([y, x], 8);
    if (marker) marker.remove();
    marker = L.marker([y, x]).addTo(map).bindPopup(`${esc(item.canonical_name || item.entity_text)}<br>CBDB:${esc(item.source_id || '')}`);
    marker.openPopup();
  }, 80);
}

document.querySelectorAll('.entity[data-authority-id]').forEach(node => {
  node.addEventListener('click', () => selectAuthority(node.dataset.authorityId));
});
document.querySelectorAll('.authority-btn[data-authority-id]').forEach(node => {
  node.addEventListener('click', () => selectAuthority(node.dataset.authorityId));
});
"""


if __name__ == "__main__":
    main()
