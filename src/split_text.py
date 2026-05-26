from __future__ import annotations

import re
from dataclasses import dataclass


CHAPTER_PATTERNS = [
    re.compile(r"^第[一二三四五六七八九十百千〇零\s　]+章\s*.*$"),
    re.compile(r"^卷[一二三四五六七八九十百千上下中〇零\s　]+.*$"),
    re.compile(r"^第[\s　]*[一二三四五六七八九十百千〇零]+[\s　]*回\s*.*$"),
    re.compile(r"^#{1,2}\s+.+$"),
]

SOURCE_LINE_PATTERN = re.compile(r"^\s*\d+@(.*)@\d+\s*$")


@dataclass
class Paragraph:
    paragraph_id: str
    chapter_id: str
    text: str


@dataclass
class Chapter:
    chapter_id: str
    title: str


def is_chapter_title(line: str) -> bool:
    text = line.strip()
    return any(pattern.match(text) for pattern in CHAPTER_PATTERNS)


def clean_source_line(line: str) -> str:
    match = SOURCE_LINE_PATTERN.match(line)
    if match:
        return match.group(1).rstrip()
    return line.rstrip()


def split_text(text: str) -> tuple[list[dict], list[dict]]:
    chapters: list[Chapter] = []
    paragraphs: list[Paragraph] = []
    current_chapter = Chapter(chapter_id="ch_0001", title="未分章")
    chapters.append(current_chapter)
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = "\n".join(part for part in buffer if part.strip()).strip()
        if content:
            paragraph_id = f"p_{len(paragraphs) + 1:06d}"
            paragraphs.append(Paragraph(paragraph_id, current_chapter.chapter_id, content))
        buffer = []

    for raw_line in text.splitlines():
        line = clean_source_line(raw_line)
        if is_chapter_title(line):
            flush()
            title = line.lstrip("#").strip()
            if chapters and chapters[-1].title == "未分章" and not paragraphs:
                chapters.pop()
            current_chapter = Chapter(chapter_id=f"ch_{len(chapters) + 1:04d}", title=title)
            chapters.append(current_chapter)
            continue
        if not line.strip():
            flush()
            continue
        buffer.append(line)
        flush()

    flush()
    return ([chapter.__dict__ for chapter in chapters], [paragraph.__dict__ for paragraph in paragraphs])
