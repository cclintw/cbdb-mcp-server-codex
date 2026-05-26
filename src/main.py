from __future__ import annotations

import argparse
from pathlib import Path

from html_exporter import export_html
from split_text import split_text
from utils import read_json, read_text, write_json


OUTPUT_DIR = Path("data/output")


def main() -> None:
    parser = argparse.ArgumentParser(description="Split historical text and export MARKUS-like annotated HTML.")
    parser.add_argument("--input", required=True, help="Input text path, e.g. data/input/sample.txt")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    text = read_text(args.input)
    chapters, paragraphs = split_text(text)

    write_json(output_dir / "chapters.json", chapters)
    write_json(output_dir / "paragraphs.json", paragraphs)

    authority_path = output_dir / "authority_table.json"
    authority_table = read_json(authority_path, [])
    if not authority_path.exists():
        write_json(authority_path, [])

    export_html(
        chapters=chapters,
        paragraphs=paragraphs,
        authority_table=authority_table,
        output_path=output_dir / "annotated.html",
    )

    print(f"Wrote {output_dir / 'chapters.json'}")
    print(f"Wrote {output_dir / 'paragraphs.json'}")
    print(f"Wrote {authority_path}")
    print(f"Wrote {output_dir / 'annotated.html'}")


if __name__ == "__main__":
    main()
