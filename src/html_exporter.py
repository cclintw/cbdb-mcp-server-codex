from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from annotator import annotate_text


DEFAULT_TEMPLATE = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CBDB MCP Annotation Demo</title>
  <style>
    body { margin: 0; color: #1f2933; background: #f7f8fa; font-family: -apple-system, BlinkMacSystemFont, "Noto Sans TC", "PingFang TC", sans-serif; }
    header { position: sticky; top: 0; padding: 16px 22px; border-bottom: 1px solid #d8dee8; background: #fff; }
    h1 { margin: 0; font-size: 20px; }
    .layout { display: grid; grid-template-columns: 260px minmax(0, 1fr) 320px; min-height: calc(100vh - 58px); }
    aside { padding: 16px; background: #fff; overflow: auto; }
    .chapters { border-right: 1px solid #d8dee8; }
    .authority { border-left: 1px solid #d8dee8; }
    main { padding: 28px 36px 64px; background: #fff; }
    article { max-width: 900px; margin: 0 auto 42px; }
    article h2 { border-bottom: 1px solid #d8dee8; padding-bottom: 8px; }
    p { font-family: "Noto Serif TC", "Songti TC", serif; font-size: 18px; line-height: 1.95; text-indent: 2em; white-space: pre-wrap; }
    a { color: inherit; text-decoration: none; }
    .chapter-list { display: grid; gap: 6px; padding: 0; list-style: none; }
    .entity { padding: 0 .1em; border-bottom: 2px solid transparent; border-radius: 3px; }
    .entity.person { background: #fff0b8; border-bottom-color: #d49a00; }
    .entity.place { background: #dff3e6; border-bottom-color: #2f8c56; }
    .entity.office { background: #d9e9ff; border-bottom-color: #2b6fb8; }
    .entity.reign { background: #ffe0cc; border-bottom-color: #c46227; }
    .authority-item { margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #e8edf3; font-size: 14px; line-height: 1.55; }
    .muted { color: #657080; }
    footer { position: fixed; left: 0; right: 0; bottom: 0; padding: 12px 16px; border-top: 1px solid #d8dee8; background: rgba(255,255,255,.96); color: #657080; text-align: center; font-size: 13px; }
    @media (max-width: 900px) { .layout { display: block; } aside { border: 0; border-bottom: 1px solid #d8dee8; } main { padding: 22px 18px 54px; } }
  </style>
</head>
<body>
  <header><h1>《水滸傳》 <span class="muted">CBDB MCP Annotation Demo</span></h1></header>
  <div class="layout">
    <aside class="chapters">
      <h2>章節</h2>
      <ol class="chapter-list">
        {% for chapter in chapters %}
          <li><a href="#{{ chapter.chapter_id }}">{{ "%03d"|format(loop.index) }} {{ chapter.title }}</a></li>
        {% endfor %}
      </ol>
    </aside>
    <main>
      {% for chapter in chapters %}
        <article id="{{ chapter.chapter_id }}">
          <h2>{{ chapter.title }}</h2>
          {% for paragraph in chapter.paragraphs %}
            <p id="{{ paragraph.paragraph_id }}">{{ paragraph.annotated_html | safe }}</p>
          {% endfor %}
        </article>
      {% endfor %}
    </main>
    <aside class="authority">
      <h2>CBDB 權威表</h2>
      {% for item in authority_table %}
        <div class="authority-item">
          <strong>{{ item.entity_text }}</strong>
          {% if item.canonical_name and item.canonical_name != item.entity_text %} / {{ item.canonical_name }}{% endif %}
          <div class="muted">{{ item.entity_type }} · CBDB:{{ item.source_id }}</div>
          {% if item.source_url %}<a href="{{ item.source_url }}" target="_blank" rel="noreferrer">CBDB 參考來源</a>{% endif %}
        </div>
      {% endfor %}
    </aside>
  </div>
  <footer>本頁面為示範網頁, 內容經過亂數處理。標註來源為 ChatGPT + CBDB 資料庫( 共{{ authority_table|length }} 筆實體)</footer>
</body>
</html>
"""


def export_html(
    chapters: list[dict[str, Any]],
    paragraphs: list[dict[str, Any]],
    authority_table: list[dict[str, Any]],
    output_path: str | Path,
    template_dir: str | Path = "templates",
) -> None:
    template_path = Path(template_dir) / "annotated.html.j2"
    if template_path.exists():
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template("annotated.html.j2")
    else:
        env = Environment(autoescape=select_autoescape(["html", "xml"]))
        template = env.from_string(DEFAULT_TEMPLATE)

    chapter_map = {chapter["chapter_id"]: {**chapter, "paragraphs": []} for chapter in chapters}
    for paragraph in paragraphs:
        rendered = {**paragraph, "annotated_html": annotate_text(paragraph["text"], authority_table)}
        chapter_map.setdefault(
            paragraph["chapter_id"],
            {"chapter_id": paragraph["chapter_id"], "title": "未分章", "paragraphs": []},
        )["paragraphs"].append(rendered)

    html = template.render(chapters=list(chapter_map.values()), authority_table=authority_table)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
