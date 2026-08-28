#!/usr/bin/env python3
"""Turn a GitHub markdown open book (chapters-md.txt) into a DeepRead edition."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from catalog_io import upsert_local_books

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
PUBLIC_BOOKS = ROOT / "public" / "books"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^```")
FENCE_BLOCK_RE = re.compile(r"(^```[^\n]*\n.*?^```[ \t]*\n?)", re.M | re.S)
MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
BR_RE = re.compile(r"<br\s*/?>", re.I)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FOOTNOTE_RE = re.compile(r"^footnote:\s*", re.I)
GITHUB_REPO = "https://github.com/stas00/ml-engineering/blob/master"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
SKIP_FILES = {"build/README.md", "SKILL.md", "todo.md"}
SKIP_H2_TITLES = {"table of contents", "subsections"}
SPLIT_MIN_LINES = 400
SPLIT_MIN_H2 = 3
SPLIT_ALWAYS_H2 = 8
SPLIT_ALWAYS_LINES = 700
SMALL_SECTION_WORDS = 35

PARTS: list[tuple[str, tuple[str, ...], str]] = [
    (
        "Part 1. Insights",
        ("insights/",),
        "What you need to know before you buy, rent, or train: the AI battlefield, cloud choices, and when a GPU upgrade is actually worth it.",
    ),
    (
        "Part 2. Hardware",
        ("compute/", "storage/", "network/"),
        "Accelerators, CPUs, memory, storage, and the intra- and inter-node networks that keep those accelerators fed.",
    ),
    (
        "Part 3. Orchestration",
        ("orchestration/",),
        "Containers, Kubernetes, and SLURM — the job of getting GPUs allocated, launched, and kept alive.",
    ),
    (
        "Part 4. Training",
        ("training/",),
        "Model parallelism, performance, fault tolerance, instabilities, dtypes, checkpoints, and the rest of the training stack.",
    ),
    (
        "Part 5. Inference",
        ("inference/",),
        "Serving large models: KV cache, parallelism at decode time, and the software that actually ships tokens.",
    ),
    (
        "Part 6. Development",
        ("debug/", "testing/"),
        "Debugging multi-GPU PyTorch, hanging collectives, and tests that still work when the cluster does not.",
    ),
    (
        "Part 7. Notes",
        ("resources/", "contributors.md", "courses/"),
        "Training chronicles, contributors, and a compact lessons-learned course through the same material.",
    ),
]


@dataclass
class OpenBookSpec:
    id: str
    title: str
    author: str
    subtitle: str
    year: int
    topics: list[str] = field(default_factory=list)
    source_url: str = ""
    source_label: str = ""
    repo_url: str = GITHUB_REPO


@dataclass
class Chunk:
    title: str
    github_anchor: str
    heading_level: int
    body: str
    kind: str  # "intro" | "h2"


@dataclass
class Page:
    title: str
    slug: str
    level: int
    body: str
    source: str
    in_tree: bool = True
    in_pages: bool = True
    heading_ids: dict[str, str] = field(default_factory=dict)


def slugify(title: str) -> str:
    text = strip_md(title).lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:90] or "section"


def reader_heading_id(title: str) -> str:
    text = strip_md(title).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def github_anchor(title: str) -> str:
    text = strip_md(title).lower()
    text = re.sub(r"[^-_a-z0-9\s]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


def strip_md(text: str) -> str:
    text = re.sub(r"!?\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', "'") + '"'


def unique_slug(base: str, seen: dict[str, int]) -> str:
    seen[base] = seen.get(base, 0) + 1
    return base if seen[base] == 1 else f"{base}-{seen[base]}"


def unique_anchor(base: str, seen: dict[str, int]) -> str:
    n = seen.get(base, 0)
    seen[base] = n + 1
    return base if n == 0 else f"{base}-{n}"


def transform_prose(markdown: str, fn) -> str:
    pieces: list[str] = []
    pos = 0
    for match in FENCE_BLOCK_RE.finditer(markdown):
        pieces.append(fn(markdown[pos : match.start()]))
        pieces.append(match.group(0))
        pos = match.end()
    pieces.append(fn(markdown[pos:]))
    return "".join(pieces)


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


def shift_headings(markdown: str, delta: int) -> str:
    if delta == 0:
        return markdown

    def shift_prose(prose: str) -> str:
        lines: list[str] = []
        for line in prose.splitlines(keepends=True):
            match = HEADING_RE.match(line.rstrip("\n"))
            if not match:
                lines.append(line)
                continue
            level = max(1, min(6, len(match.group(1)) + delta))
            newline = "\n" if line.endswith("\n") else ""
            lines.append(f"{'#' * level} {match.group(2)}{newline}")
        return "".join(lines)

    return transform_prose(markdown, shift_prose)


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def parse_chunks(markdown: str) -> tuple[str, list[Chunk]]:
    lines = markdown.splitlines()
    title = ""
    chunks: list[Chunk] = []
    buf: list[str] = []
    current_title = ""
    current_level = 0
    current_kind = "intro"
    in_fence = False
    skipped_title = False

    def flush() -> None:
        nonlocal buf, current_title, current_level, current_kind
        body = "\n".join(buf).strip()
        buf = []
        if current_kind == "intro" and not body and not current_title:
            return
        chunks.append(
            Chunk(
                title=current_title,
                github_anchor=github_anchor(current_title) if current_title else "",
                heading_level=current_level,
                body=body,
                kind=current_kind,
            )
        )

    for line in lines:
        stripped = line.strip()
        if FENCE_RE.match(stripped):
            in_fence = not in_fence
            buf.append(line)
            continue
        if not in_fence:
            match = HEADING_RE.match(stripped)
            if match:
                level = len(match.group(1))
                heading = strip_md(match.group(2))
                if level == 1 and not skipped_title:
                    title = heading
                    skipped_title = True
                    continue
                if level <= 2:
                    flush()
                    current_title = heading
                    current_level = level
                    current_kind = "h2"
                    continue
        buf.append(line)
    flush()
    if not title:
        title = first_heading(markdown) or "Untitled"
    return title, chunks


def should_split(markdown: str, chunks: list[Chunk], source: str) -> bool:
    if source == "README.md":
        return False
    h2s = [chunk for chunk in chunks if chunk.kind == "h2"]
    lines = markdown.count("\n") + 1
    if lines >= SPLIT_ALWAYS_LINES or len(h2s) >= SPLIT_ALWAYS_H2:
        return True
    return lines >= SPLIT_MIN_LINES and len(h2s) >= SPLIT_MIN_H2


def part_for(rel: str) -> tuple[str, str] | None:
    for title, prefixes, blurb in PARTS:
        for prefix in prefixes:
            if rel == prefix.rstrip("/") or rel.startswith(prefix):
                return title, blurb
    return None


def drop_section(markdown: str, heading: str) -> str:
    target = heading.lower()
    lines = markdown.splitlines()
    out: list[str] = []
    in_fence = False
    skipping = False
    for line in lines:
        stripped = line.strip()
        if FENCE_RE.match(stripped):
            in_fence = not in_fence
        if not in_fence:
            match = HEADING_RE.match(stripped)
            if match and len(match.group(1)) == 2:
                if strip_md(match.group(2)).lower() == target:
                    skipping = True
                    continue
                skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out).strip() + "\n"


def tidy_prose(prose: str) -> str:
    prose = HTML_COMMENT_RE.sub("", prose)
    prose = BR_RE.sub(" / ", prose)
    prose = prose.replace("$$", "$")
    lines: list[str] = []
    for line in prose.splitlines(keepends=True):
        raw, ending = (line[:-1], "\n") if line.endswith("\n") else (line, "")
        if FOOTNOTE_RE.match(raw):
            lines.append("> " + FOOTNOTE_RE.sub("Footnote: ", raw, count=1) + ending)
        else:
            lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "".join(lines))


def split_link_target(target: str) -> tuple[str, str]:
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    title = ""
    if len(target) >= 2 and target[-1] in {'"', "'"}:
        quote = target[-1]
        start = target.rfind(quote, 0, len(target) - 1)
        if start > 0:
            title = target[start:]
            target = target[:start].rstrip()
    if "#" in target:
        path, anchor = target.split("#", 1)
        return path.strip(), anchor.strip()
    return target, ""


def is_remote(link: str) -> bool:
    return bool(re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", link, re.I))


def resolve_repo_path(source: Path, rel: Path, link: str) -> Path | None:
    if not link or is_remote(link):
        return None
    cleaned = link.split("?")[0].replace("\\", "/")
    candidate = (source.parent / cleaned).resolve()
    try:
        candidate.relative_to(rel)
    except ValueError:
        return None
    return candidate


def collect_chapter_files(source: Path) -> list[Path]:
    listing = source / "chapters-md.txt"
    if not listing.exists():
        raise SystemExit(f"No chapters-md.txt in {source}")
    files: list[Path] = []
    for line in listing.read_text(encoding="utf-8").splitlines():
        rel = line.strip()
        if not rel or rel in SKIP_FILES:
            continue
        path = source / rel
        if not path.is_file():
            print(f"skip missing chapter: {rel}")
            continue
        files.append(path)
    return files


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


def save_cover(source: Path, dest: Path, pdf: Path | None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for name in (
        "images/Machine-Learning-Engineering-book-cover-1275x1650.png",
        "images/Machine-Learning-Engineering-book-cover.png",
    ):
        cover = source / name
        if cover.is_file():
            pix = pymupdf.Pixmap(str(cover))
            if pix.n >= 4:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            pix.save(str(dest), jpg_quality=86)
            return
    if pdf and pdf.is_file():
        doc = pymupdf.open(pdf)
        page = doc[0]
        pix = page.get_pixmap(dpi=140, alpha=False)
        if pix.n >= 4:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        pix.save(str(dest), jpg_quality=86)
        doc.close()
        return
    raise SystemExit("No cover image found in the source repo")


def nest(entries: list[dict]) -> list[dict]:
    root: list[dict] = []
    stack: list[dict] = []
    for entry in entries:
        node = {
            "title": entry["title"],
            "slug": entry["slug"],
            "level": entry["level"],
            "children": [],
        }
        while stack and stack[-1]["level"] >= node["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            root.append(node)
        stack.append(node)
    return root


def heading_id_map(body: str, page_slug: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    seen: dict[str, int] = {}
    github_seen: dict[str, int] = {}
    in_fence = False
    for line in body.splitlines():
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line.strip())
        if not match or len(match.group(1)) != 2:
            continue
        base = reader_heading_id(match.group(2))
        if not base:
            continue
        raw = unique_anchor(base, seen)
        gh = unique_anchor(github_anchor(match.group(2)), github_seen)
        target = f"{page_slug}--{raw}"
        mapping[raw] = target
        mapping[gh] = target
    return mapping


def ingest(source: Path, spec: OpenBookSpec, pdf: Path | None) -> None:
    source = source.resolve()
    pages_dir = CONTENT / spec.id / "pages"
    figures_dir = PUBLIC_BOOKS / spec.id / "figures"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    if figures_dir.exists():
        shutil.rmtree(figures_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    save_cover(source, PUBLIC_BOOKS / spec.id / "cover.jpg", pdf)

    chapter_files = collect_chapter_files(source)
    slug_seen: dict[str, int] = {}
    pages: list[Page] = []
    file_pages: dict[str, list[Page]] = {}
    anchor_targets: dict[tuple[str, str], str] = {}
    file_slugs: dict[str, str] = {}
    figure_count = 0
    copied: dict[Path, str] = {}

    def add_page(title: str, level: int, body: str, rel: str, preferred: str | None = None) -> Page:
        slug = unique_slug(preferred or slugify(title), slug_seen)
        page = Page(title=title, slug=slug, level=level, body=body, source=rel)
        pages.append(page)
        file_pages.setdefault(rel, []).append(page)
        return page

    preface_raw = drop_section((source / "README.md").read_text(encoding="utf-8"), "Table of Contents")
    preface_title, preface_chunks = parse_chunks(preface_raw)
    preface_body = "\n\n".join(
        (f"## {chunk.title}\n\n{chunk.body}" if chunk.kind == "h2" and chunk.title else chunk.body)
        for chunk in preface_chunks
        if chunk.body or chunk.kind == "intro"
    )
    add_page("Preface", 1, preface_body, "README.md", "preface")
    file_slugs["README.md"] = "preface"

    current_part = ""
    for path in chapter_files:
        rel = path.relative_to(source).as_posix()
        if rel == "README.md":
            continue
        part = part_for(rel)
        if part and part[0] != current_part:
            current_part = part[0]
            add_page(part[0], 1, part[1], f"part:{part[0]}", slugify(part[0]))
        raw = path.read_text(encoding="utf-8")
        title, chunks = parse_chunks(raw)
        intro = next((chunk.body for chunk in chunks if chunk.kind == "intro"), "")
        h2s = [chunk for chunk in chunks if chunk.kind == "h2"]
        split = should_split(raw, chunks, rel)
        chapter = add_page(title, 2, intro, rel)
        file_slugs[rel] = chapter.slug
        file_slugs[str(path.parent.relative_to(source).as_posix())] = chapter.slug
        if path.name == "README.md":
            file_slugs[str(path.parent.relative_to(source).as_posix()) + "/"] = chapter.slug

        if not split:
            bodies = [intro] if intro else []
            for chunk in h2s:
                if chunk.title.lower() in SKIP_H2_TITLES:
                    continue
                heading = f"## {chunk.title}" if chunk.title else ""
                bodies.append(f"{heading}\n\n{chunk.body}".strip())
            chapter.body = "\n\n".join(part for part in bodies if part).strip()
            continue

        kept_on_landing: list[str] = [intro] if intro else []
        children: list[Page] = []
        for chunk in h2s:
            if chunk.title.lower() in SKIP_H2_TITLES:
                continue
            if word_count(chunk.body) < SMALL_SECTION_WORDS:
                heading = f"## {chunk.title}" if chunk.title else ""
                kept_on_landing.append(f"{heading}\n\n{chunk.body}".strip())
                continue
            child = add_page(chunk.title, 3, shift_headings(chunk.body, -1), rel)
            children.append(child)
            gh = chunk.github_anchor
            if gh:
                anchor_targets[(rel, gh)] = child.slug
                anchor_targets[(rel, slugify(chunk.title))] = child.slug
        chapter.body = "\n\n".join(part for part in kept_on_landing if part).strip()
        if not chapter.body and children:
            links = "\n".join(f"- [{child.title}](#{child.slug})" for child in children)
            chapter.body = f"This chapter covers:\n\n{links}"

    for rel, group in file_pages.items():
        if rel.startswith("part:"):
            continue
        landing = group[0]
        anchor_targets[(rel, "")] = landing.slug
        for page in group:
            page.heading_ids = heading_id_map(page.body, page.slug)
            for gh, target in page.heading_ids.items():
                anchor_targets.setdefault((rel, gh), target)
            if page.level >= 3:
                anchor_targets.setdefault((rel, github_anchor(page.title)), page.slug)
                anchor_targets.setdefault((rel, slugify(page.title)), page.slug)

    def rewrite_prose(prose: str, rel: str, page: Page) -> str:
        nonlocal figure_count

        def replace(match: re.Match[str]) -> str:
            nonlocal figure_count
            bang = match.group(0).startswith("!")
            text, raw_target = match.group(1), match.group(2)
            link, anchor = split_link_target(raw_target)
            if not link and anchor:
                target = anchor_targets.get((rel, anchor)) or page.heading_ids.get(anchor)
                if target:
                    return f"[{text}](#{target})"
                return match.group(0)
            if is_remote(link) or link.startswith("mailto:"):
                return match.group(0)
            dest = resolve_repo_path(source / rel, source, link)
            if dest is None:
                return match.group(0)
            if dest.suffix.lower() in IMAGE_EXTS and dest.is_file():
                if dest not in copied:
                    stored = dest.relative_to(source).as_posix().replace("/", "-")
                    copied[dest] = f"/books/{spec.id}/figures/{stored}"
                    shutil.copy2(dest, figures_dir / stored)
                    figure_count += 1
                if bang:
                    return f"![{text or dest.stem}]({copied[dest]})"
                return f"[{text}]({copied[dest]})"
            dest_rel = None
            if dest.is_dir() and (dest / "README.md").is_file():
                dest_rel = (dest / "README.md").relative_to(source).as_posix()
            elif dest.suffix == ".md":
                dest_rel = dest.relative_to(source).as_posix()
            elif dest.with_suffix(".md").is_file():
                dest_rel = dest.with_suffix(".md").relative_to(source).as_posix()
            elif (dest / "README.md").is_file():
                dest_rel = (dest / "README.md").relative_to(source).as_posix()
            if dest_rel and dest_rel in file_slugs:
                if anchor:
                    target = anchor_targets.get((dest_rel, anchor)) or file_slugs[dest_rel]
                else:
                    target = file_slugs[dest_rel]
                return f"[{text}](#{target})"
            try:
                github = dest.relative_to(source).as_posix()
            except ValueError:
                return match.group(0)
            url = f"{spec.repo_url}/{github}"
            if anchor:
                url += f"#{anchor}"
            return f"[{text}]({url})"

        return MD_LINK_RE.sub(replace, tidy_prose(prose))

    for page in pages:
        if page.source.startswith("part:"):
            continue
        page.body = transform_prose(
            page.body, lambda prose, current=page: rewrite_prose(prose, current.source, current)
        ).strip()

    tree_entries: list[dict] = []
    pages_meta: list[dict] = []
    words = 0
    order = 0
    for page in pages:
        words += word_count(page.body)
        filename = f"{order:03d}-{page.slug}.md"
        write_page(pages_dir / filename, page.title, page.slug, page.level, order + 1, order, page.body)
        pages_meta.append(
            {
                "title": page.title,
                "slug": page.slug,
                "level": page.level,
                "page": order + 1,
                "file": filename,
                "order": order,
            }
        )
        tree_entries.append({"title": page.title, "slug": page.slug, "level": page.level})
        if page.level <= 2 and not page.source.startswith("part:"):
            split_anchors = {
                github_anchor(child.title)
                for child in pages
                if child.source == page.source and child.level == 3
            }
            in_fence = False
            heading_seen: dict[str, int] = {}
            for line in page.body.splitlines():
                if FENCE_RE.match(line.strip()):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                match = HEADING_RE.match(line.strip())
                if not match or len(match.group(1)) != 2:
                    continue
                title = strip_md(match.group(2))
                if github_anchor(title) in split_anchors:
                    continue
                raw = unique_anchor(reader_heading_id(title), heading_seen)
                tree_entries.append({"title": title, "slug": f"{page.slug}--{raw}", "level": 3})
        order += 1

    pages_est = max(len(pages_meta), round(words / 280) if words else 1)
    nav = {
        "id": spec.id,
        "title": spec.title,
        "author": spec.author,
        "subtitle": spec.subtitle,
        "year": spec.year,
        "topics": spec.topics,
        "pages": pages_est,
        "cover": f"/books/{spec.id}/cover.jpg",
        "printPages": False,
        "tree": nest(tree_entries),
        "pagesMeta": pages_meta,
    }
    (CONTENT / spec.id / "nav.json").write_text(json.dumps(nav, indent=2) + "\n", encoding="utf-8")
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
    parser = argparse.ArgumentParser(description="Ingest a GitHub markdown open book into DeepRead.")
    parser.add_argument("source", type=Path, help="Path to the cloned book repository")
    parser.add_argument("--id", default="ml-engineering")
    parser.add_argument("--title", default="Machine Learning Engineering")
    parser.add_argument("--author", default="Stas Bekman")
    parser.add_argument("--subtitle", default="Open notes on training and serving large models")
    parser.add_argument("--year", type=int, default=dt.date.today().year)
    parser.add_argument("--topic", action="append", dest="topics", default=[])
    parser.add_argument("--source-url", default="https://github.com/stas00/ml-engineering")
    parser.add_argument("--source-label", default="GitHub · stas00/ml-engineering")
    parser.add_argument("--repo-url", default=GITHUB_REPO)
    parser.add_argument("--pdf", type=Path, default=None, help="Optional print PDF used only as a cover fallback")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    source = args.source.expanduser()
    if not source.is_dir():
        print(f"Source directory not found: {source}", file=sys.stderr)
        sys.exit(1)
    topics = args.topics or ["ML engineering", "Training", "GPUs", "Inference"]
    pdf = args.pdf.expanduser() if args.pdf else None
    ingest(
        source,
        OpenBookSpec(
            id=args.id,
            title=args.title,
            author=args.author,
            subtitle=args.subtitle,
            year=args.year,
            topics=topics,
            source_url=args.source_url,
            source_label=args.source_label,
            repo_url=args.repo_url,
        ),
        pdf,
    )
