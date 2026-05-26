from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from annotator import annotate_text


def export_html(
    chapters: list[dict[str, Any]],
    paragraphs: list[dict[str, Any]],
    authority_table: list[dict[str, Any]],
    output_path: str | Path,
    template_dir: str | Path = "templates",
) -> None:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("annotated.html.j2")
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
