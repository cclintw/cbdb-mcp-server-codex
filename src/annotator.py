from __future__ import annotations

import html
from typing import Any


TYPE_CLASS = {
    "person": "person",
    "place": "place",
    "office": "office",
    "reign": "reign",
}


def annotate_text(text: str, authority_table: list[dict[str, Any]]) -> str:
    if not authority_table:
        return html.escape(text)

    authorities = sorted(
        [item for item in authority_table if item.get("entity_text")],
        key=lambda item: len(item["entity_text"]),
        reverse=True,
    )
    output: list[str] = []
    i = 0
    while i < len(text):
        match = next((item for item in authorities if text.startswith(item["entity_text"], i)), None)
        if match:
            entity_text = match["entity_text"]
            output.append(render_span(entity_text, match))
            i += len(entity_text)
        else:
            output.append(html.escape(text[i]))
            i += 1
    return "".join(output)


def render_span(entity_text: str, authority: dict[str, Any]) -> str:
    entity_type = authority.get("entity_type", "entity")
    css_class = TYPE_CLASS.get(entity_type, "entity")
    authority_id = html.escape(str(authority.get("authority_id", "")), quote=True)
    source = html.escape(str(authority.get("source", "")), quote=True)
    source_id = html.escape(str(authority.get("source_id", "")), quote=True)
    canonical = html.escape(str(authority.get("canonical_name", entity_text)), quote=True)
    title = f"{canonical} / {source}:{source_id}".strip()
    return (
        f'<span class="entity {css_class}" '
        f'data-authority-id="{authority_id}" '
        f'data-source="{source}" '
        f'data-source-id="{source_id}" '
        f'title="{title}">{html.escape(entity_text)}</span>'
    )
