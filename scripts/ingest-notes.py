#!/usr/bin/env python3
"""Turn a chapter-per-folder markdown notes repo into a DeepRead book."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import pymupdf

from catalog_io import upsert_local_books

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
PUBLIC_BOOKS = ROOT / "public" / "books"

CHAPTER_DIR_RE = re.compile(r"^(\d+)\.")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^```")
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.I)
DIV_WRAP_RE = re.compile(r"<div\b[^>]*>\s*(.*?)\s*</div>", re.I | re.S)
BR_RE = re.compile(r"<br\s*/?>", re.I)
LEFTOVER_HTML_RE = re.compile(r"</?(?:div|span|p|section|center)\b[^>]*>", re.I)


@dataclass
class NotesSpec:
    id: str
    title: str
    author: str
    subtitle: str
    year: int
    topics: list[str] = field(default_factory=list)
    source_url: str = ""
    source_label: str = ""
    kicker: str = "NOTES"


class ImgAttrParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.attrs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        for key, value in attrs:
            if value is not None:
                self.attrs[key.lower()] = value


def slugify(title: str) -> str:
    text = title.lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:90] or "section"


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', "'") + '"'


def chapter_markdown(folder: Path) -> Path | None:
    for name in ("Readme.md", "README.md"):
        path = folder / name
        if path.exists():
            return path
    found = sorted(folder.glob("*.md"))
    return found[0] if found else None


def first_heading(markdown: str) -> str | None:
    in_fence = False
    for line in markdown.splitlines():
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line.strip())
        if match:
            return strip_md(match.group(2))
    return None


def strip_md(text: str) -> str:
    text = text.replace("**", "").replace("__", "").replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def demote_extra_h1(markdown: str) -> str:
    lines: list[str] = []
    in_fence = False
    skipped_title = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if FENCE_RE.match(stripped):
            in_fence = not in_fence
            lines.append(line)
            continue
        if not in_fence:
            match = HEADING_RE.match(stripped)
            if match and match.group(1) == "#" and not skipped_title:
                skipped_title = True
                continue
            if match and match.group(1) == "#":
                lines.append("## " + match.group(2))
                continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def parse_img_attrs(tag: str) -> dict[str, str]:
    parser = ImgAttrParser()
    try:
        parser.feed(tag)
        if parser.attrs:
            return parser.attrs
    except Exception:
        pass
    attrs: dict[str, str] = {}
    for match in re.finditer(
        r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))',
        tag,
    ):
        attrs[match.group(1).lower()] = match.group(2) or match.group(3) or match.group(4) or ""
    return attrs


def resolve_image(chapter_dir: Path, src: str) -> Path | None:
    cleaned = src.strip().split("?")[0].replace("\\", "/")
    if cleaned.startswith(("http://", "https://", "data:")):
        return None
    rel = Path(cleaned)
    for candidate in (chapter_dir / rel, chapter_dir / "images" / rel.name):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def rewrite_images(
    markdown: str, chapter_dir: Path, chapter_no: int, dest_dir: Path, book_id: str
) -> tuple[str, int]:
    used = 0

    def replace_tag(tag: str) -> str:
        nonlocal used
        attrs = parse_img_attrs(tag)
        src = attrs.get("src")
        if not src:
            return ""
        source = resolve_image(chapter_dir, src)
        if source is None:
            print(f"  missing image: {src}")
            return ""
        name = f"{chapter_no:02d}-{source.name}"
        shutil.copy2(source, dest_dir / name)
        used += 1
        alt = attrs.get("alt") or source.stem.replace("-", " ").replace("_", " ")
        return f"![{alt}](/books/{book_id}/figures/{name})"

    def replace_div(match: re.Match[str]) -> str:
        inner = match.group(1)
        tags = IMG_TAG_RE.findall(inner)
        if not tags:
            return inner.strip()
        return "\n\n".join(replace_tag(tag) for tag in tags)

    markdown = DIV_WRAP_RE.sub(replace_div, markdown)
    markdown = IMG_TAG_RE.sub(lambda match: replace_tag(match.group(0)), markdown)
    markdown = BR_RE.sub("\n", markdown)
    markdown = LEFTOVER_HTML_RE.sub("", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown, used


def write_page(path: Path, title: str, slug: str, level: int, page: int, order: int, body: str) -> None:
    path.write_text(
        (
            "---\n"
            f"title: {yaml_quote(title)}\n"
            f"slug: {slug}\n"
            f"level: {level}\n"
            f"page: {page}\n"
            f"order: {order}\n"
            "---\n\n"
            f"{body.strip()}\n"
        ),
        encoding="utf-8",
    )


def write_cover(path: Path, spec: NotesSpec) -> None:
    width, height = 720, 1080
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    navy = (0.09, 0.13, 0.20)
    cream = (0.95, 0.92, 0.86)
    gold = (0.76, 0.62, 0.38)
    page.draw_rect(page.rect, color=None, fill=navy)
    page.draw_rect(pymupdf.Rect(28, 28, width - 28, height - 28), color=cream, width=0.7)
    page.draw_rect(pymupdf.Rect(36, 36, width - 36, height - 36), color=gold, width=0.35)

    for index in range(7):
        x = 110 + index * 72
        y = 210 + (index % 3) * 18
        page.draw_circle(pymupdf.Point(x, y), 3.2, color=None, fill=gold)
        if index < 6:
            page.draw_line(
                pymupdf.Point(x, y),
                pymupdf.Point(x + 72, 210 + ((index + 1) % 3) * 18),
                color=gold,
                width=0.4,
            )

    page.insert_textbox(
        pymupdf.Rect(72, 300, width - 72, 340),
        spec.kicker,
        fontsize=11,
        fontname="helv",
        color=gold,
    )
    page.insert_textbox(
        pymupdf.Rect(72, 360, width - 72, 620),
        spec.title.replace(" — ", "\n").replace(": ", "\n"),
        fontsize=36,
        fontname="hebo",
        color=cream,
    )
    page.draw_rect(pymupdf.Rect(72, 648, 168, 651), color=None, fill=gold)
    if spec.subtitle:
        page.insert_textbox(
            pymupdf.Rect(72, 672, width - 72, 780),
            spec.subtitle,
            fontsize=16,
            fontname="helv",
            color=cream,
        )
    page.insert_textbox(
        pymupdf.Rect(72, 960, width - 72, 1010),
        spec.author,
        fontsize=16,
        fontname="hebo",
        color=cream,
    )
    pix = page.get_pixmap(dpi=120, alpha=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(path), jpg_quality=88)
    doc.close()


def preface_body(spec: NotesSpec) -> str:
    source = ""
    if spec.source_url:
        label = spec.source_label or spec.source_url
        source = f" They were ingested from [{label}]({spec.source_url})."
    return f"""\
These notes were imported into DeepRead as a chapter-per-folder markdown edition.{source}

Chapters stay intact, diagrams are copied into the book figures folder, and HTML figure markup is converted to markdown.

## How to read

Start at the first chapter and follow the section list in the sidebar.
"""


def further_reading_body(readme: Path, spec: NotesSpec) -> str:
    text = readme.read_text(encoding="utf-8")
    marker = re.search(r"^#+\s+Additonal Resources|^#+\s+Additional Resources", text, re.I | re.M)
    body = text[marker.start() :] if marker else ""
    body = re.sub(r"^#+\s+Additonal Resources\s*", "## Further reading\n\n", body, count=1, flags=re.I)
    body = re.sub(r"^#+\s+Additional Resources\s*", "## Further reading\n\n", body, count=1, flags=re.I)
    if not body.strip():
        if spec.source_url:
            label = spec.source_label or spec.source_url
            body = f"See the [source notes]({spec.source_url}) ({label}) for extra papers and talks."
        else:
            body = "See the original notes repository for extra papers and talks."
    return body.strip() + "\n"


def ingest(source: Path, spec: NotesSpec) -> None:
    pages_dir = CONTENT / spec.id / "pages"
    figures_dir = PUBLIC_BOOKS / spec.id / "figures"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    if figures_dir.exists():
        shutil.rmtree(figures_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    chapters = sorted(
        [path for path in source.iterdir() if path.is_dir() and CHAPTER_DIR_RE.match(path.name)],
        key=lambda path: int(CHAPTER_DIR_RE.match(path.name).group(1)),  # type: ignore[union-attr]
    )
    write_cover(PUBLIC_BOOKS / spec.id / "cover.jpg", spec)

    pages_meta: list[dict] = []
    tree: list[dict] = []
    figure_count = 0
    words = 0
    order = 0

    def add_page(title: str, slug: str, level: int, body: str) -> None:
        nonlocal order, words
        page_number = order + 1
        filename = f"{order:03d}-{slug}.md"
        write_page(pages_dir / filename, title, slug, level, page_number, order, body)
        pages_meta.append(
            {
                "title": title,
                "slug": slug,
                "level": level,
                "page": page_number,
                "file": filename,
                "order": order,
            }
        )
        tree.append({"title": title, "slug": slug, "level": level, "children": []})
        words += len(body.split())
        order += 1

    add_page("Preface", "preface", 2, preface_body(spec))

    for folder in chapters:
        md_path = chapter_markdown(folder)
        if md_path is None:
            print(f"skip (no markdown): {folder.name}")
            continue
        chapter_no = int(CHAPTER_DIR_RE.match(folder.name).group(1))  # type: ignore[union-attr]
        raw = md_path.read_text(encoding="utf-8")
        title = first_heading(raw) or re.sub(r"^\d+\.\s*", "", folder.name).strip()
        body, used = rewrite_images(demote_extra_h1(raw), folder, chapter_no, figures_dir, spec.id)
        figure_count += used
        add_page(title, slugify(title), 2, body)
        print(f"{chapter_no:02d} {title} ({used} figures)")

    readme = source / "Readme.md"
    if not readme.exists():
        readme = source / "README.md"
    if readme.exists():
        add_page("Further reading", "further-reading", 2, further_reading_body(readme, spec))

    pages_est = max(len(pages_meta), round(words / 280) if words else 1)
    (CONTENT / spec.id / "nav.json").write_text(
        json.dumps(
            {
                "id": spec.id,
                "title": spec.title,
                "author": spec.author,
                "subtitle": spec.subtitle,
                "year": spec.year,
                "topics": spec.topics,
                "pages": pages_est,
                "cover": f"/books/{spec.id}/cover.jpg",
                "tree": tree,
                "pagesMeta": pages_meta,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    entry = {
        "id": spec.id,
        "title": spec.title,
        "author": spec.author,
        "subtitle": spec.subtitle,
        "year": spec.year,
        "topics": spec.topics,
        "pages": pages_est,
        "sections": len(pages_meta),
        "figures": figure_count,
        "cover": f"/books/{spec.id}/cover.jpg",
        "startSlug": pages_meta[0]["slug"],
    }
    if spec.source_url:
        entry["sourceUrl"] = spec.source_url
        entry["sourceLabel"] = spec.source_label or spec.source_url
    upsert_local_books([entry])
    print(f"{spec.id}: {len(pages_meta)} sections, {figure_count} figures, ~{pages_est} pages")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turn a chapter-per-folder markdown notes repo into a DeepRead book."
    )
    parser.add_argument("source", type=Path, help="Path to the notes repository")
    parser.add_argument("--id", required=True, help="Book id used in URLs and on disk")
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--year", type=int, default=dt.date.today().year)
    parser.add_argument("--topic", action="append", dest="topics", default=[])
    parser.add_argument("--source-url", default="")
    parser.add_argument("--source-label", default="")
    parser.add_argument("--kicker", default="NOTES")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    source = args.source.expanduser()
    if not source.is_dir():
        print(f"Source directory not found: {source}", file=sys.stderr)
        sys.exit(1)
    ingest(
        source,
        NotesSpec(
            id=args.id,
            title=args.title,
            author=args.author,
            subtitle=args.subtitle,
            year=args.year,
            topics=args.topics,
            source_url=args.source_url,
            source_label=args.source_label,
            kicker=args.kicker,
        ),
    )
