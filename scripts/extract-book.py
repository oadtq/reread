#!/usr/bin/env python3
"""Extract print PDFs into structured markdown, figures, and covers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from catalog_io import upsert_local_books

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
PUBLIC_BOOKS = ROOT / "public" / "books"

FIGURE_RE = re.compile(r"^(?:Figure|FIGURE)\s+((?:[A-Z]\.)?\d+(?:[.-]\d+)?)\s*[.:]?", re.I)
CAPTION_VERB_RE = re.compile(r"^(shows|show|illustrates|illustrated|depicts)\b", re.I)
FIGURE_DPI = 288
SECTION_HEAD_RE = re.compile(r"^\d+(?:\.\d+)+\s+\S")
CHAPTER_LINE_RE = re.compile(r"^(CHAPTER|APPENDIX|PART)\s+([0-9A-Z]+)$", re.I)
OPENER_LABEL = {"chapter": "Chapter", "appendix": "Appendix", "part": "Part"}
HYPHEN_RE = re.compile(r"^(.*?)([A-Za-z0-9.]+)([`*]*)[-‐‑‒–]([`*]*)\s*$")
KEEP_HYPHEN = {"to", "re", "pre", "co", "ex", "in", "un", "non", "e", "x"}
COMPOUND_SECONDS = {
    "leading", "function", "functions", "based", "only", "purpose", "centric",
    "defined", "threaded", "precision", "aware", "specific", "quality", "point",
}
OPENER_LABELS = {"CHAPTER", "APPENDIX"}
DOT_LEADERS = re.compile(r"\.{5,}|…{2,}|[.]{3,}\s*\d+\s*$")
BOLD_FLAG = 16


@dataclass
class BookSpec:
    id: str
    pdf: Path
    title: str
    author: str
    subtitle: str
    year: int
    topics: list[str]
    cover_page: int
    profile: str
    skip_toc: list[str] = field(default_factory=list)
    source_url: str = ""
    source_label: str = ""


SPEC_PATH = Path(__file__).with_name("books.json")
EXAMPLE_SPEC_PATH = Path(__file__).with_name("books.example.json")


def load_specs(only_id: str | None = None) -> list[BookSpec]:
    if not SPEC_PATH.exists():
        print(
            f"Missing {SPEC_PATH.name}. Copy {EXAMPLE_SPEC_PATH.name} to {SPEC_PATH.name} "
            "and point each `pdf` at a book you have the right to extract.",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    items = payload["books"] if isinstance(payload, dict) else payload
    specs = [
        BookSpec(
            id=item["id"],
            pdf=Path(item["pdf"]).expanduser(),
            title=item["title"],
            author=item["author"],
            subtitle=item.get("subtitle", ""),
            year=int(item["year"]),
            topics=list(item.get("topics", [])),
            cover_page=int(item["cover_page"]),
            profile=item["profile"],
            skip_toc=list(item.get("skip_toc", [])),
            source_url=item.get("source_url", ""),
            source_label=item.get("source_label", ""),
        )
        for item in items
    ]
    if only_id:
        specs = [spec for spec in specs if spec.id == only_id]
        if not specs:
            print(f"No book with id {only_id!r} in {SPEC_PATH.name}.", file=sys.stderr)
            sys.exit(1)
    missing = [spec for spec in specs if not spec.pdf.is_file()]
    if missing:
        for spec in missing:
            print(f"PDF not found for {spec.id}: {spec.pdf}", file=sys.stderr)
        sys.exit(1)
    return specs


def figure_caption_id(text: str, size: float | None = None, italic: bool = False) -> str | None:
    """True figure labels, not body sentences like 'Figure 4.1 shows…'."""
    match = FIGURE_RE.match(text.strip())
    if not match:
        return None
    rest = text.strip()[match.end() :].strip()
    if CAPTION_VERB_RE.match(rest):
        return None
    if size is not None and size >= 10.6 and rest and not rest.startswith(":"):
        return None
    if rest and rest[:1].islower() and not italic:
        return None
    return match.group(1)


def slugify(title: str) -> str:
    text = title.lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:90] or "section"


def norm(text: str) -> str:
    text = text.lower().replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"[^a-z0-9]+", "", text)


def fix_ligatures(text: str) -> str:
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
    text = re.sub(r"fi\s+(?=[a-z])", "fi", text)
    text = re.sub(r"fl\s+(?=[a-z])", "fl", text)
    text = re.sub(r"ff\s+(?=[a-z])", "ff", text)
    return text


MATH_TRANSLATE = str.maketrans(
    {
        "¼": "=",
        "¾": "=",
        "þ": "+",
        "ð": "(",
        "Þ": ")",
        "½": "[",
        "\x01": "×",
        "\x02": "×",
        "\x03": "×",
        "\x04": "×",
        "\x05": "−",
    }
)
CODEISH_RE = re.compile(
    r"^(?:__[A-Za-z][A-Za-z0-9_]*__"
    r"|[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*"
    r"|[A-Za-z_][A-Za-z0-9_]*\[\]"
    r"|[a-z]+[A-Z][A-Za-z0-9_]*)$"
)
CUDA_TOKEN_RE = re.compile(
    r"(?<![`\w])(__[A-Za-z][A-Za-z0-9_]*__|[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*|[A-Za-z_][A-Za-z0-9_]*\[\])(?![`\w])"
)


def is_math_font(font: str) -> bool:
    lower = font.lower()
    return (
        "math" in lower
        or "symbol" in lower
        or font.startswith("AdvPi")
        or "4C4E74" in font
        or font in {"AdvPA7F4", "AdvP4C4E46", "AdvP4C4E59"}
    )


CODE_LINE_RATIO = 0.8
EXAMPLE_CAPTION_RE = re.compile(r"^Example\s+\d+[.-]\d+", re.I)
CAPTION_LANG_RE = [
    (re.compile(r"\bcypher\b", re.I), "cypher"),
    (re.compile(r"\bsparql\b", re.I), "sparql"),
    (re.compile(r"\bturtle\b|\bnotation\s*3\b|\bn3\b", re.I), "turtle"),
    (re.compile(r"\brdf/?xml\b", re.I), "xml"),
    (re.compile(r"\bjson\b", re.I), "json"),
    (re.compile(r"\bxml\b", re.I), "xml"),
    (re.compile(r"\bprotocol\s*buffers?\b|\bprotobuf\b", re.I), "protobuf"),
    (re.compile(r"\bthrift\b", re.I), "thrift"),
    (re.compile(r"\bavro\b", re.I), "avro"),
    (re.compile(r"\bdatalog\b", re.I), "datalog"),
    (re.compile(r"\bsql\b|relational schema", re.I), "sql"),
    (re.compile(r"\bjavascript\b|\bnode\.js\b", re.I), "javascript"),
    (re.compile(r"\bpython\b", re.I), "python"),
    (re.compile(r"\bjava\b", re.I), "java"),
    (re.compile(r"\bcuda\b|\bc\+\+\b", re.I), "cpp"),
    (re.compile(r"\bcss\b", re.I), "css"),
    (re.compile(r"\bruby\b", re.I), "ruby"),
    (re.compile(r"\bbash\b|\bshell\b", re.I), "bash"),
]


def is_code_font(font: str) -> bool:
    lower = font.lower()
    return any(token in lower for token in ("cour", "mono", "consol", "typewriter")) or font in {
        "AdvP9011",
        "AdvP900D",
        "AdvP4C4E51",
    }


def line_code_ratio(spans: list[dict]) -> float:
    """Share of visible characters set in a monospace/code font."""
    code_n = 0
    total = 0
    for span in spans:
        chunk = (span.get("text") or "").strip()
        if not chunk:
            continue
        n = len(chunk)
        total += n
        if is_code_font(span.get("font") or ""):
            code_n += n
    return code_n / total if total else 0.0


def is_italic_font(font: str, flags: int) -> bool:
    if flags & 2:
        return True
    lower = font.lower()
    return "italic" in lower or "oblique" in lower or lower.endswith("-obl") or "696A" in font


def remap_math(text: str) -> str:
    text = text.replace("\x021", "−∞").replace("þ1", "+∞")
    text = text.translate(MATH_TRANSLATE)
    return text.replace("6=", "≠")


def md_escape_code(text: str) -> str:
    ticks = "`"
    while ticks in text:
        ticks += "`"
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{ticks}{pad}{text}{pad}{ticks}"


def wrap_style(style: str, text: str) -> str:
    if not text.strip() or style in {"text", "math"}:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()) :]
    inner = text.strip()
    if style == "code":
        return f"{lead}{md_escape_code(inner)}{trail}"
    if style == "italic":
        return f"{lead}*{inner.replace('*', '\\*')}*{trail}"
    if style == "bold":
        return f"{lead}**{inner}**{trail}"
    return text


def span_style(span: dict, raw: str) -> str:
    font = span.get("font") or ""
    flags = span.get("flags") or 0
    bold = bool(flags & BOLD_FLAG) or "Bold" in font or "bold" in font.lower()
    token = re.sub(r"^[\s.,;:()]+|[\s.,;:()]+$", "", raw.strip())
    if is_math_font(font):
        return "math"
    if is_code_font(font) or (token and CODEISH_RE.match(token) and token.lower().rstrip(".") not in {"e.g", "i.e"}):
        return "code"
    if is_italic_font(font, flags):
        return "italic"
    if bold:
        return "bold"
    return "text"


def spans_to_markdown(spans: list[dict]) -> str:
    sizes = [span["size"] for span in spans if span.get("text", "").strip()]
    line_size = max(sizes) if sizes else 0
    pieces: list[tuple[str, str]] = []
    for span in spans:
        if line_size and span.get("size", line_size) < line_size * 0.75:
            continue
        raw = fix_ligatures(span["text"].replace("\u2003", " ").replace("\t", " "))
        if is_math_font(span.get("font") or ""):
            raw = remap_math(raw)
        if not raw:
            continue
        chunks: list[tuple[str, str | None]] = [(raw, None)]
        split = re.match(r"^(.*\S)(\s*)\*$", raw)
        code_star = is_code_font(span.get("font") or "")
        if split and split.group(1).strip() not in {"*", "×"} and not code_star:
            chunks = [(split.group(1), None), (split.group(2) + "×", "math")]
        elif raw.strip() in {"*", "∗"} and not code_star:
            chunks = [("×", "math")]
        for chunk, forced in chunks:
            style = forced or span_style(span, chunk)
            if pieces and pieces[-1][0] == style:
                pieces[-1] = (style, pieces[-1][1] + chunk)
            else:
                pieces.append((style, chunk))
    wrapped: list[str] = []
    for style, chunk in pieces:
        if style in {"text", "math"}:
            chunk = re.sub(r"(?<=[\dA-Za-z\)])\*(?=[\dA-Za-z\(])", "×", chunk)
        wrapped.append(wrap_style(style, chunk))
    text = "".join(wrapped)

    def keep_or_code(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.lower().rstrip(".") in {"e.g", "i.e"}:
            return token
        return md_escape_code(token)

    parts = re.split(r"(`+[^`]*`+)", text)
    text = "".join(
        CUDA_TOKEN_RE.sub(keep_or_code, part) if index % 2 == 0 else part
        for index, part in enumerate(parts)
    )
    text = re.sub(r"`(\S+)`(?=[A-Za-z])", r"`\1` ", text)
    return re.sub(r" {2,}", " ", text).strip()


def ends_with_break_hyphen(text: str) -> bool:
    return bool(HYPHEN_RE.match(text.rstrip()))


def join_hyphen(previous: str, current: str) -> str:
    match = HYPHEN_RE.match(previous.rstrip())
    if not match:
        return previous.rstrip() + " " + current
    head, last = match.group(1), match.group(2)
    rest = current.lstrip()
    while rest[:1] in {"*", "`"}:
        rest = rest[1:]
    nxt = re.match(r"^([A-Za-z0-9.]+)", rest)
    word = nxt.group(1) if nxt else ""
    if last.lower() in KEEP_HYPHEN or word.lower() in COMPOUND_SECONDS:
        glued = last + "-" + rest
    else:
        glued = last + rest
    return head + glued


def join_wrapped(previous: str, current: str) -> str:
    prev, cur = previous.rstrip(), current.lstrip()
    if prev.endswith("*") and cur.startswith("*"):
        return prev[:-1] + " " + cur[1:]
    return prev + " " + cur


def toc_entries(doc: pymupdf.Document, spec: BookSpec) -> list[dict]:
    skip = {norm(item) for item in spec.skip_toc}
    entries = []
    for level, title, page in doc.get_toc():
        title = re.sub(r"\s+", " ", title).strip()
        lowered = title.lower()
        if norm(title) in skip or lowered.startswith("in praise"):
            continue
        if lowered == "introduction" and entries and entries[-1]["page"] == page:
            continue
        entries.append({"level": level, "title": title, "page": page, "slug": slugify(title)})
    seen: dict[str, int] = {}
    for entry in entries:
        base = entry["slug"]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            entry["slug"] = f"{base}-{seen[base]}"
    return entries


def collect_lines(page: pymupdf.Page, page_no: int, spec: BookSpec, figure_clips: list[pymupdf.Rect] | None = None) -> list[dict]:
    records: list[dict] = []
    clips = figure_clips or []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans") or []
            if not spans:
                continue
            plain_parts = []
            for span in spans:
                chunk = span["text"].replace("\u2003", " ").replace("\t", "    ")
                if is_math_font(span.get("font") or ""):
                    chunk = remap_math(chunk)
                plain_parts.append(chunk)
            joined = fix_ligatures("".join(plain_parts))
            code_line = line_code_ratio(spans) >= CODE_LINE_RATIO
            text = joined.rstrip() if code_line else re.sub(r"\s+", " ", joined).strip()
            if not text.strip():
                continue
            size = max(span["size"] for span in spans)
            x0, y0, x1, y1 = line["bbox"]
            line_rect = pymupdf.Rect(x0, y0, x1, y1)
            if size < 8.6 and any(overlap_ratio(line_rect, clip) > 0.45 for clip in clips):
                continue
            if spec.profile == "inference" and size <= 7.7 and y0 < 50:
                continue
            if spec.profile == "elsevier":
                page_h = page.cropbox.height
                header_footer = y0 < 45 or y0 > page_h - 36
                if header_footer and not FIGURE_RE.search(text):
                    continue
                if DOT_LEADERS.search(text):
                    continue
                if size < 9.2 and not FIGURE_RE.search(text) and not code_line:
                    continue
                if re.fullmatch(r"\d+", text) and size < 12:
                    continue
            if spec.profile == "oreilly":
                page_h = page.cropbox.height
                if y0 > page_h - 55 and size <= 10:
                    continue
                if size <= 8.2 and not code_line:
                    continue
                if DOT_LEADERS.search(text):
                    continue
            markdown = text if code_line else (spans_to_markdown(spans) or text)
            records.append(
                {
                    "text": text,
                    "md": markdown,
                    "size": size,
                    "bold": any((span.get("flags", 0) & BOLD_FLAG) or "Bold" in span.get("font", "") for span in spans),
                    "italic": any(is_italic_font(span.get("font") or "", span.get("flags") or 0) for span in spans),
                    "code_line": code_line,
                    "x": x0,
                    "x1": x1,
                    "y": y0,
                    "y1": y1,
                    "page": page_no,
                }
            )
    records.sort(key=lambda rec: (rec["y"], rec["x"]))
    return merge_same_row(records)


def overlap_ratio(inner: pymupdf.Rect, outer: pymupdf.Rect) -> float:
    inter = inner & outer
    if inner.width * inner.height <= 1:
        return 0.0
    return (inter.width * inter.height) / (inner.width * inner.height)


def merge_same_row(records: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for rec in records:
        if (
            merged
            and rec["size"] >= 12
            and merged[-1]["size"] >= 12
            and rec["page"] == merged[-1]["page"]
            and abs(rec["y"] - merged[-1]["y"]) < 3
            and rec["size"] < 20
            and not rec.get("code_line")
            and not merged[-1].get("code_line")
        ):
            merged[-1]["text"] = merged[-1]["text"] + " " + rec["text"]
            merged[-1]["md"] = merged[-1]["md"] + " " + rec["md"]
            merged[-1]["x1"] = max(merged[-1]["x1"], rec["x1"])
            continue
        merged.append(rec)
    return merged


def reorder_two_column(records: list[dict], spec: BookSpec) -> list[dict]:
    """Read left column then right on O'Reilly glossary-style pages."""
    if spec.profile != "oreilly" or len(records) < 20:
        return records
    left = [rec for rec in records if rec["x"] < 200]
    right = [rec for rec in records if rec["x"] >= 200]
    left_body = [rec for rec in left if rec["size"] < 14]
    right_body = [rec for rec in right if rec["size"] < 14]
    if len(left_body) < 8 or len(right_body) < 8:
        return records
    display = [rec for rec in records if rec["size"] >= 18]
    left_rest = sorted((rec for rec in left if rec["size"] < 18), key=lambda rec: (rec["y"], rec["x"]))
    right_rest = sorted((rec for rec in right if rec["size"] < 18), key=lambda rec: (rec["y"], rec["x"]))
    return display + left_rest + right_rest


def merge_display_titles(records: list[dict]) -> list[dict]:
    out: list[dict] = []
    index = 0
    while index < len(records):
        rec = records[index]
        match = CHAPTER_LINE_RE.match(rec["text"])
        if match:
            kind, number = match.group(1).title(), match.group(2)
            titles: list[str] = []
            cursor = index + 1
            while (
                cursor < len(records)
                and records[cursor]["page"] == rec["page"]
                and records[cursor]["size"] >= 20
            ):
                titles.append(records[cursor]["text"])
                cursor += 1
            label = OPENER_LABEL.get(kind.lower(), kind.title())
            if kind.lower() in {"appendix", "part"}:
                number = number.upper()
            title = " ".join(titles).strip()
            rec = {
                **rec,
                "text": f"{label} {number}: {title}" if title else f"{label} {number}",
                "md": f"{label} {number}: {title}" if title else f"{label} {number}",
                "size": 36,
                "kind": "heading",
            }
            out.append(rec)
            index = cursor
            continue
        if rec["text"].strip().upper() == "CHAPTER":
            titles: list[str] = []
            number = ""
            cursor = index + 1
            while cursor < len(records) and records[cursor]["page"] == rec["page"]:
                nxt = records[cursor]
                if re.fullmatch(r"\d+", nxt["text"]) and nxt["size"] >= 18:
                    number = nxt["text"]
                    cursor += 1
                    continue
                if nxt["size"] >= 16:
                    raw = nxt["text"].strip()
                    numbered = re.search(r"^(.*\S)\s+(\d+)$", raw)
                    if numbered and not number:
                        titles.append(numbered.group(1))
                        number = numbered.group(2)
                    else:
                        titles.append(raw)
                    cursor += 1
                    continue
                break
            if number and titles:
                title = " ".join(titles)
                rec = {
                    **rec,
                    "text": f"Chapter {number}: {title}",
                    "md": f"Chapter {number}: {title}",
                    "size": 36,
                    "kind": "heading",
                }
                out.append(rec)
                index = cursor
                continue
        out.append(rec)
        index += 1
    return bind_display_openers(out)


def bind_display_openers(records: list[dict]) -> list[dict]:
    """CHAPTER/APPENDIX labels can sit above or below a giant stacked title."""
    by_page: dict[int, list[int]] = {}
    for index, rec in enumerate(records):
        by_page.setdefault(rec["page"], []).append(index)
    drop: set[int] = set()
    for idxs in by_page.values():
        label_i = next(
            (
                i
                for i in idxs
                if records[i]["text"].strip().upper() in OPENER_LABELS and records[i].get("kind") != "heading"
            ),
            None,
        )
        if label_i is None:
            continue
        kind = OPENER_LABEL.get(records[label_i]["text"].strip().lower(), records[label_i]["text"].strip().title())
        number = ""
        titles: list[str] = []
        started = False
        for i in idxs:
            if i == label_i or i in drop:
                continue
            rec = records[i]
            raw = rec["text"].strip()
            if rec["size"] >= 40 and re.fullmatch(r"[A-Z0-9]+", raw):
                number = raw
                drop.add(i)
                started = True
                continue
            if rec["size"] < 18:
                if started or "CONTENTS" in raw.upper() or raw.upper() == "INTRODUCTION":
                    break
                continue
            trailing = re.search(r"^(.*\S)\s+([A-Z0-9]+)$", raw)
            if trailing and not number:
                titles.append(trailing.group(1))
                number = trailing.group(2)
            else:
                titles.append(raw)
            drop.add(i)
            started = True
        if not number and not titles:
            continue
        composed = f"{kind} {number}: {' '.join(titles).strip()}" if number else f"{kind}: {' '.join(titles).strip()}"
        records[label_i] = {
            **records[label_i],
            "text": composed.strip(" :"),
            "md": composed.strip(" :"),
            "size": 36,
            "kind": "heading",
        }
    return [rec for index, rec in enumerate(records) if index not in drop]


def strip_md_marks(text: str) -> str:
    return re.sub(r"[*`]", "", text).strip()


def recent_example_caption(blocks: list[dict]) -> str:
    if not blocks:
        return ""
    plain = strip_md_marks(blocks[-1]["text"])
    return plain if EXAMPLE_CAPTION_RE.match(plain) else ""


def guess_code_language(body: str, caption: str = "") -> str:
    for pattern, lang in CAPTION_LANG_RE:
        if caption and pattern.search(caption):
            return lang
    text = body.strip()
    if re.search(r"^#!/", text) or re.search(r"^\s*\$\s+\w+", text, re.M):
        return "bash"
    if text.startswith("{") or text.startswith("["):
        return "json"
    if re.match(r"^<\?xml\b|^<rdf:|^<[A-Za-z]", text):
        return "xml"
    if re.search(r"^@prefix\b", text, re.M | re.I):
        return "turtle"
    if re.search(r"^message\s+\w+\s*\{", text, re.M) or re.search(
        r"^\s*(required|optional|repeated)\s+\w+.*=\s*\d+", text, re.M
    ):
        return "protobuf"
    if re.search(r"^struct\s+\w+\s*\{", text, re.M):
        return "thrift"
    if re.search(r"^record\s+\w+\s*\{", text, re.M):
        return "avro"
    if re.search(
        r"\bCREATE\s+TABLE\b|\bPRIMARY\s+KEY\b|\bBEGIN\s+TRANSACTION\b|\bFOR\s+UPDATE\b|"
        r"\bSELECT\b.+\bFROM\b|\bALTER\s+TABLE\b|\bUPDATE\s+\w+\s+SET\b",
        text,
        re.I | re.S,
    ):
        return "sql"
    if re.search(r"\bPREFIX\b.+\bSELECT\b|\bSELECT\b.+\bWHERE\s*\{", text, re.I | re.S):
        return "sparql"
    if re.search(r"\bMATCH\b|\bRETURN\b|-\[:[A-Za-z_]", text):
        return "cypher"
    if re.search(r"__global__|__device__|__shared__|cudaMalloc", text):
        return "cpp"
    if re.search(r"^[\w.#*:>-][\w.#*\s:>-]*\{\s*[\w-]+\s*:", text, re.S):
        return "css"
    if re.search(r"\bHash\.new\b|\.each\s+do\s+\|", text):
        return "ruby"
    if re.search(r"\bdef\s+\w+\(|\bimport\s+\w+", text):
        return "python"
    if re.search(r"\b(function|const|let|var|=>)\b|\b===\b|\.aggregate\(", text):
        return "javascript"
    if re.search(r"\bawk\b.+\bsort\b|\buniq\s+-c\b", text):
        return "bash"
    return ""


def code_records_to_text(recs: list[dict]) -> str:
    if not recs:
        return ""
    base_x = min(rec["x"] for rec in recs)
    char_w = max(4.0, recs[0]["size"] * 0.55)
    same_page_gaps = [
        nxt["y"] - prev["y"]
        for prev, nxt in zip(recs, recs[1:])
        if nxt["page"] == prev["page"] and 0 < nxt["y"] - prev["y"] < 40
    ]
    typical = sorted(same_page_gaps)[len(same_page_gaps) // 2] if same_page_gaps else recs[0]["size"] * 1.2
    lines: list[str] = []
    for index, rec in enumerate(recs):
        if index:
            prev = recs[index - 1]
            if rec["page"] == prev["page"] and rec["y"] - prev["y"] > typical * 1.55:
                lines.append("")
        extra = max(0, round((rec["x"] - base_x) / char_w))
        text = rec["text"]
        if extra and not text.startswith(" "):
            text = " " * extra + text
        lines.append(text)
    return "\n".join(lines)


def fence_code(body: str, lang: str) -> str:
    ticks = "```"
    while ticks in body:
        ticks += "`"
    return f"{ticks}{lang}\n{body.rstrip()}\n{ticks}"


def classify(rec: dict, spec: BookSpec) -> str:
    text = rec["text"]
    if rec.get("kind") == "heading":
        return "heading"
    if rec.get("code_line"):
        return "code"
    if spec.profile == "oreilly":
        if rec["size"] >= 15.5 or CHAPTER_LINE_RE.match(text):
            return "heading"
        fig = FIGURE_RE.match(text)
        if fig:
            rest = text[fig.end() :].strip()
            if rec.get("italic") or not rest or rest[:1].isupper():
                return "caption"
        if text.startswith("•"):
            return "list"
        return "body"
    if spec.profile == "inference":
        if rec["size"] >= 12 or SECTION_HEAD_RE.match(text):
            return "heading"
        if (FIGURE_RE.match(text) and rec["size"] < 10.6) or (rec["size"] <= 7.7 and rec["y"] >= 50):
            return "caption"
        if 7.7 < rec["size"] < 8.6:
            return "table"
    else:
        if (
            rec["size"] >= 13
            or (text.isupper() and rec["size"] >= 12 and len(text) > 8)
            or (SECTION_HEAD_RE.match(text) and rec["size"] >= 11.8)
        ):
            return "heading"
        if text.upper() in {"CHAPTER CONTENTS", "APPENDIX CONTENTS", "CONTENTS"} or (
            "CONTENTS" in text.upper() and rec["size"] < 14 and len(text) < 40
        ):
            return "skip"
        if rec["size"] < 10.6 and (FIGURE_RE.search(text) or rec["size"] <= 10.0):
            return "caption"
    if text.startswith("•"):
        return "list"
    return "body"


def attach_kinds(records: list[dict], spec: BookSpec) -> list[dict]:
    kept = []
    for rec in records:
        rec["kind"] = rec.get("kind") or classify(rec, spec)
        if rec["kind"] != "skip":
            kept.append(rec)
    pages_with_figure = {
        rec["page"] for rec in kept if rec["kind"] == "caption" and FIGURE_RE.search(rec["text"])
    }
    for rec in kept:
        if rec["kind"] != "caption" or FIGURE_RE.search(rec["text"]):
            continue
        if rec["page"] not in pages_with_figure:
            rec["kind"] = "body"
    for index, rec in enumerate(kept):
        previous = kept[index - 1] if index else None
        continue_caption = (
            previous
            and previous["kind"] == "caption"
            and rec["kind"] == "body"
            and rec["page"] == previous["page"]
            and rec["size"] < 10.6
        )
        if spec.profile == "oreilly":
            caption_open = previous and (
                ends_with_break_hyphen(previous["text"])
                or not re.search(r'[.!?]"?$', previous["text"].rstrip())
            )
            continue_caption = bool(
                continue_caption
                and caption_open
                and rec.get("italic")
                and rec["text"][:1].islower()
            )
        if continue_caption:
            rec["kind"] = "caption"
    return kept


def join_text(parts: list[str]) -> str:
    text = parts[0]
    for part in parts[1:]:
        if ends_with_break_hyphen(text):
            text = join_hyphen(text, part)
        else:
            text = join_wrapped(text, part)
    return re.sub(r"\s+", " ", text).strip()


def join_caption(parts: list[str]) -> str:
    labels = [part for part in parts if FIGURE_RE.search(part)]
    rest = [part for part in parts if not FIGURE_RE.search(part)]
    return join_text(labels + rest) if labels else join_text(parts)


def strip_bullet(text: str) -> str:
    return re.sub(r"^[-•]\s*", "", text)


def flush_paragraph(kind: str, parts: list[str]) -> dict | None:
    if not parts:
        return None
    text = join_text(parts)
    if kind == "list":
        text = "- " + strip_bullet(text)
    return {"kind": kind, "text": text}


def oreilly_lines_wrap(last: dict, nxt: dict, wrap_gap: float) -> bool:
    """Join wrapped print lines without gluing the next paragraph or list item."""
    if nxt["page"] == last["page"] + 1:
        return not re.search(r'[.!?]"?$', last["text"]) and (
            nxt["text"][:1].islower() or ends_with_break_hyphen(last["text"])
        )
    if nxt["page"] != last["page"]:
        return False
    if re.match(r"^\d+\.\s", nxt["text"]):
        return False
    # Two-column pages continue from the bottom of the left column into the top of the right.
    if (
        last["x"] < 200 <= nxt["x"]
        and last["y"] > 520
        and nxt["y"] < 320
        and (nxt["text"][:1].islower() or ends_with_break_hyphen(last["text"]))
    ):
        return True
    gap = nxt["y"] - last["y1"]
    if not -4 <= gap <= wrap_gap:
        return False
    if nxt["x"] - last["x"] < 10:
        return True
    return nxt["text"][:1].islower() or ends_with_break_hyphen(last["text"])


def records_to_blocks(records: list[dict], spec: BookSpec | None = None) -> list[dict]:
    wrap_gap = 1.0 if spec and spec.profile == "oreilly" else 8
    blocks: list[dict] = []
    index = 0
    while index < len(records):
        rec = records[index]
        kind = rec["kind"]
        if kind == "table":
            table_recs = [rec]
            index += 1
            while index < len(records) and records[index]["kind"] == "table":
                nxt = records[index]
                prev = table_recs[-1]
                if nxt["page"] != prev["page"] or nxt["y"] - prev["y"] > 36:
                    break
                table_recs.append(nxt)
                index += 1
            markdown = table_to_markdown(table_recs)
            if markdown:
                blocks.append({"kind": "table", "text": markdown, "page": rec["page"]})
            continue
        if kind == "heading":
            blocks.append({"kind": "heading", "text": rec["text"], "page": rec["page"]})
            index += 1
            continue
        if kind == "caption":
            parts = [rec["text"]]
            index += 1
            while index < len(records) and records[index]["kind"] == "caption":
                nxt = records[index]
                if FIGURE_RE.search(nxt["text"]) and any(FIGURE_RE.search(part) for part in parts):
                    break
                parts.append(nxt["text"])
                index += 1
            blocks.append({"kind": "caption", "text": join_caption(parts), "page": rec["page"]})
            continue
        if kind == "code":
            code_recs = [rec]
            index += 1
            while index < len(records) and records[index]["kind"] == "code":
                nxt = records[index]
                prev = code_recs[-1]
                if nxt["page"] > prev["page"] + 1:
                    break
                if nxt["page"] == prev["page"] and nxt["y"] - prev["y"] > 36:
                    break
                code_recs.append(nxt)
                index += 1
            body = code_records_to_text(code_recs)
            lang = guess_code_language(body, recent_example_caption(blocks))
            blocks.append({"kind": "code", "text": fence_code(body, lang), "page": rec["page"]})
            continue
        parts = [strip_bullet(rec["md"]) if kind == "list" else rec["md"]]
        last = rec
        index += 1
        while index < len(records):
            nxt = records[index]
            if spec and spec.profile == "oreilly":
                gap_ok = oreilly_lines_wrap(last, nxt, wrap_gap)
            else:
                indented = nxt["x"] >= last["x"] + 10
                same_page = (
                    nxt["page"] == last["page"]
                    and (nxt["y"] - last["y1"]) <= wrap_gap
                    and not indented
                )
                across_page = (
                    nxt["page"] == last["page"] + 1
                    and not re.search(r'[.!?]"?$', last["text"])
                    and (nxt["text"][:1].islower() or ends_with_break_hyphen(last["text"]))
                )
                gap_ok = same_page or across_page
            list_wrap = kind == "list" and nxt["kind"] == "body" and gap_ok
            body_wrap = kind == nxt["kind"] == "body" and gap_ok
            if not list_wrap and not body_wrap:
                break
            parts.append(strip_bullet(nxt["md"]) if kind == "list" else nxt["md"])
            last = nxt
            index += 1
        block = flush_paragraph(kind, parts)
        if block:
            block["page"] = rec["page"]
            blocks.append(block)
    return blocks


def cluster_columns(xs: list[float]) -> list[float]:
    xs = sorted(xs)
    cols: list[float] = []
    for x in xs:
        if not cols or x - cols[-1] > 28:
            cols.append(x)
        else:
            cols[-1] = (cols[-1] + x) / 2
    return cols


def col_index(x: float, cols: list[float]) -> int:
    return min(range(len(cols)), key=lambda i: abs(cols[i] - x))


def table_to_markdown(records: list[dict]) -> str | None:
    if len(records) < 4:
        return None
    cols = cluster_columns([rec["x"] for rec in records])
    if len(cols) < 2:
        return None
    rows: list[list[str]] = []
    current: list[str] | None = None
    last_y: float | None = None
    for rec in sorted(records, key=lambda item: (item["y"], item["x"])):
        if last_y is None or rec["y"] - last_y > 14:
            current = [""] * len(cols)
            rows.append(current)
        assert current is not None
        slot = col_index(rec["x"], cols)
        current[slot] = (current[slot] + " " + rec["text"]).strip()
        last_y = rec["y"]
    rows = [row for row in rows if any(row)]
    if len(rows) < 2:
        return None

    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", " ").strip()

    header = rows[0]
    body = rows[1:]
    lines = [
        "| " + " | ".join(cell(item) for item in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(cell(item) for item in padded[: len(header)]) + " |")
    return "\n".join(lines)


def union_rect(boxes: list[tuple[float, float, float, float]]) -> pymupdf.Rect:
    return pymupdf.Rect(
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def is_hairline(box: tuple[float, float, float, float]) -> bool:
    width, height = box[2] - box[0], box[3] - box[1]
    return (height < 2.8 and width > 36) or (width < 2.8 and height > 36)


def rects_near(a: tuple[float, float, float, float], b: tuple[float, float, float, float], gap: float) -> bool:
    padded = pymupdf.Rect(a[0] - gap, a[1] - gap, a[2] + gap, a[3] + gap)
    return padded.intersects(pymupdf.Rect(b))


def native_to_page_clip(page: pymupdf.Page, rect: pymupdf.Rect) -> pymupdf.Rect:
    mapped = pymupdf.Rect(rect)
    if page.rotation:
        mapped = mapped * page.rotation_matrix
    return mapped & page.rect


def page_to_native_clip(page: pymupdf.Page, rect: pymupdf.Rect) -> pymupdf.Rect:
    mapped = pymupdf.Rect(rect)
    if page.rotation:
        mapped = mapped * page.derotation_matrix
    return mapped & page.cropbox


def tighten_to_ink(page: pymupdf.Page, clip: pymupdf.Rect, pad: float = 10) -> pymupdf.Rect:
    pix = page.get_pixmap(clip=clip, dpi=36, alpha=False)
    samples = pix.samples
    width, height, n = pix.width, pix.height, pix.n
    min_x, min_y, max_x, max_y = width, height, 0, 0
    for y in range(0, height, 2):
        row = y * width * n
        for x in range(0, width, 2):
            i = row + x * n
            if samples[i] < 248 or samples[i + 1] < 248 or samples[i + 2] < 248:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if max_x <= min_x or max_y <= min_y:
        return clip
    scale = 36 / 72
    tight = pymupdf.Rect(
        clip.x0 + min_x / scale - pad,
        clip.y0 + min_y / scale - pad,
        clip.x0 + (max_x + 1) / scale + pad,
        clip.y0 + (max_y + 1) / scale + pad,
    )
    return tight & clip


def overlay_trim(clip: pymupdf.Rect, overlay: pymupdf.Rect, page_rect: pymupdf.Rect) -> pymupdf.Rect:
    """Shrink clip to exclude a header or caption that sits along one edge."""
    ow, oh = overlay.width, overlay.height
    if ow >= max(oh * 1.8, 72) and overlay.y0 > page_rect.height * 0.38:
        clip.y1 = min(clip.y1, overlay.y0 - 8)
    elif ow >= max(oh * 1.8, 72) and overlay.y1 < page_rect.height * 0.62:
        clip.y0 = max(clip.y0, overlay.y1 + 8)
    elif oh >= max(ow * 1.8, 72) and overlay.x0 > page_rect.width * 0.38:
        clip.x1 = min(clip.x1, overlay.x0 - 8)
    elif oh >= max(ow * 1.8, 72) and overlay.x1 < page_rect.width * 0.62:
        clip.x0 = max(clip.x0, overlay.x1 + 8)
    return clip


def rotated_plate_clip(page: pymupdf.Page, caption_boxes: list[pymupdf.Rect]) -> pymupdf.Rect | None:
    native = page.cropbox
    clip = pymupdf.Rect(page.rect) + (32, 24, -10, -10)
    header_native = pymupdf.Rect(native.x0, native.y0, native.x1, min(native.y0 + 44, native.y1))
    clip = overlay_trim(clip, header_native * page.rotation_matrix, page.rect)
    caption = None
    for box in caption_boxes:
        mapped = pymupdf.Rect(box) * page.rotation_matrix
        caption = mapped if caption is None else (caption | mapped)
    if caption is not None:
        clip = overlay_trim(clip, caption, page.rect)
    clip &= page.rect
    if clip.width < 40 or clip.height < 24:
        return None
    return tighten_to_ink(page, clip)


def nearby_caption_boxes(
    caption: pymupdf.Rect,
    extras: list[pymupdf.Rect],
) -> list[pymupdf.Rect]:
    boxes = [pymupdf.Rect(caption)]
    padded = pymupdf.Rect(caption) + (-36, -36, 36, 36)
    for extra in extras:
        if padded.intersects(extra):
            boxes.append(pymupdf.Rect(extra))
    return boxes


def cluster_figure_clip(
    caption_y: float,
    prev_y: float,
    page: pymupdf.Page,
    images: list[tuple[float, float, float, float]],
    drawings: list[tuple[float, float, float, float]],
    labels: list[tuple[float, float, float, float]],
) -> pymupdf.Rect | None:
    native = page.cropbox
    top = max(prev_y + 2, native.y0 + 40)
    bottom = min(caption_y - 2, native.y1 - 6)
    if bottom <= top:
        return None
    image_set = set(images)
    candidates: list[tuple[float, float, float, float]] = []
    for box in images + drawings + labels:
        if box[3] < top or box[1] > bottom:
            continue
        if box in image_set:
            candidates.append(box)
            continue
        if box[1] < native.y0 + 36:
            continue
        width = box[2] - box[0]
        if is_hairline(box) and width > native.width * 0.65 and box[1] < native.y0 + 52:
            continue
        candidates.append(box)
    if not candidates:
        return None
    seeds = [box for box in candidates if 0 <= caption_y - box[3] <= 72]
    if not seeds:
        pictured = [box for box in candidates if box in image_set]
        pool = pictured or candidates
        seeds = [max(pool, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]))]
    cluster = list(seeds)
    changed = True
    while changed:
        changed = False
        bounds = union_rect(cluster)
        for box in candidates:
            if box in cluster:
                continue
            if rects_near((bounds.x0, bounds.y0, bounds.x1, bounds.y1), box, 18):
                cluster.append(box)
                changed = True
    clip = union_rect(cluster)
    clip += (-6, -6, 6, 6)
    clip.y1 = min(clip.y1, caption_y - 1)
    clip &= native
    if clip.width < 40 or clip.height < 24:
        return None
    return clip


def extract_figures(doc: pymupdf.Document, spec: BookSpec) -> tuple[dict[str, str], dict[int, list[pymupdf.Rect]]]:
    dest = PUBLIC_BOOKS / spec.id / "figures"
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*"):
        old.unlink()
    mapping: dict[str, str] = {}
    clips_by_page: dict[int, list[pymupdf.Rect]] = {}
    for page_index in range(doc.page_count):
        page = doc[page_index]
        data = page.get_text("dict")
        captions: list[tuple[str, pymupdf.Rect]] = []
        extras: list[pymupdf.Rect] = []
        images: list[tuple[float, float, float, float]] = []
        labels: list[tuple[float, float, float, float]] = []
        for block in data["blocks"]:
            if block.get("type") == 1:
                images.append(tuple(block["bbox"]))
                continue
            for line in block.get("lines", []):
                spans = line.get("spans") or []
                text = "".join(span["text"] for span in spans).strip()
                size = max(span["size"] for span in spans) if spans else 0
                bbox = pymupdf.Rect(line["bbox"])
                italic = any(is_italic_font(span.get("font") or "", span.get("flags") or 0) for span in spans)
                fig_id = figure_caption_id(text, size, italic=italic)
                if fig_id:
                    captions.append((fig_id, bbox))
                elif 8.6 <= size <= 10.2:
                    extras.append(bbox)
                elif spans and size <= 8.2:
                    labels.append(tuple(line["bbox"]))
        drawings: list[tuple[float, float, float, float]] = []
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect is None or (rect.width < 3 and rect.height < 3):
                continue
            drawings.append((rect.x0, rect.y0, rect.x1, rect.y1))
        captions.sort(key=lambda item: item[1].y0)
        for index, (fig_id, caption_box) in enumerate(captions):
            if fig_id in mapping:
                continue
            prev_y = captions[index - 1][1].y0 if index else 36
            if page.rotation:
                render = rotated_plate_clip(page, nearby_caption_boxes(caption_box, extras))
                clip = page_to_native_clip(page, render) if render is not None else None
            else:
                clip = cluster_figure_clip(caption_box.y0, prev_y, page, images, drawings, labels)
                render = native_to_page_clip(page, clip) if clip is not None else None
                if render is not None:
                    render += (-6, -6, 6, 6)
                    render &= page.rect
            if render is None or clip is None or render.width < 40 or render.height < 24:
                continue
            try:
                pix = page.get_pixmap(clip=render, dpi=FIGURE_DPI, alpha=False)
                if pix.n >= 4:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                name = f"fig-{fig_id.replace('.', '-')}.png"
                pix.save(str(dest / name))
                mapping[fig_id] = f"/books/{spec.id}/figures/{name}"
                clips_by_page.setdefault(page_index + 1, []).append(clip)
            except Exception as error:
                print(f"{spec.id} figure {fig_id} failed: {error}")
    return mapping, clips_by_page


def merge_split_tables(blocks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for block in blocks:
        if out and block["kind"] == "table" and out[-1]["kind"] == "table":
            prev_lines = out[-1]["text"].splitlines()
            next_lines = block["text"].splitlines()
            if len(prev_lines) >= 2 and len(next_lines) >= 2 and prev_lines[0] == next_lines[0]:
                out[-1]["text"] = "\n".join(prev_lines + next_lines[2:])
                continue
        out.append(block)
    return out


def insert_figures(blocks: list[dict], src_by_id: dict[str, str]) -> list[dict]:
    out = []
    for block in blocks:
        if block["kind"] != "caption":
            out.append(block)
            continue
        match = FIGURE_RE.search(block["text"])
        caption = re.sub(r"\s+", " ", block["text"]).strip()
        src = src_by_id.get(match.group(1)) if match else None
        if src:
            out.append({"kind": "figure", "text": f"![{caption}]({src})", "page": block["page"]})
        else:
            out.append({"kind": "caption", "text": f"*{caption}*", "page": block["page"]})
    return out


def heading_key(text: str) -> tuple[str, str] | None:
    match = re.match(r"^(chapter|appendix)\s+([0-9a-z]+)\b", text, re.I)
    if match:
        return match.group(1).lower(), match.group(2).upper()
    match = re.match(r"^part\s+([ivxlcdm]+)\b", text, re.I)
    if match:
        return "part", match.group(1).upper()
    return None


def canonicalize_headings(blocks: list[dict], entries: list[dict]) -> list[dict]:
    titles = {heading_key(entry["title"]): entry["title"] for entry in entries if heading_key(entry["title"])}
    for block in blocks:
        if block["kind"] != "heading":
            continue
        key = heading_key(block["text"])
        if key and key in titles:
            block["text"] = titles[key]
    return blocks


def reflow_around_figures(blocks: list[dict]) -> list[dict]:
    out: list[dict] = []
    index = 0
    while index < len(blocks):
        current = blocks[index]
        figure = blocks[index + 1] if index + 1 < len(blocks) else None
        following = blocks[index + 2] if index + 2 < len(blocks) else None
        if (
            current["kind"] == "body"
            and figure
            and figure["kind"] == "figure"
            and following
            and following["kind"] == "body"
            and not re.search(r'[.!?]"?$', current["text"])
            and (following["text"][:1].islower() or ends_with_break_hyphen(current["text"]))
        ):
            out.append({**current, "text": join_text([current["text"], following["text"]])})
            out.append(figure)
            index += 3
            continue
        out.append(current)
        index += 1
    return out


def split_sections(blocks: list[dict], entries: list[dict]) -> dict[int, list[dict]]:
    targets = [(index, norm(entry["title"]), entry["page"]) for index, entry in enumerate(entries)]
    starts = [-1] * len(entries)
    cursor = 0
    for block_index, block in enumerate(blocks):
        if block["kind"] != "heading" or cursor >= len(targets):
            continue
        needle = norm(block["text"])
        key = heading_key(block["text"])
        for ahead in range(cursor, min(cursor + 6, len(targets))):
            same_heading = needle == targets[ahead][1]
            same_opener = bool(key) and key == heading_key(entries[ahead]["title"])
            if same_heading or same_opener:
                starts[ahead] = block_index
                cursor = ahead + 1
                break
    for index, start in enumerate(starts):
        if start >= 0:
            continue
        page = entries[index]["page"]
        for block_index, block in enumerate(blocks):
            if block["page"] >= page:
                starts[index] = block_index
                break
        if starts[index] < 0:
            starts[index] = len(blocks)
        print(f"fallback page split: {entries[index]['title']}")
    grouped: dict[int, list[dict]] = {index: [] for index in range(len(entries))}
    bounds = starts + [len(blocks)]
    for index in range(len(entries)):
        grouped[index] = blocks[bounds[index] : bounds[index + 1]]
    return grouped


def blocks_to_markdown(blocks: list[dict], title: str) -> str:
    chunks: list[str] = []
    title_norm = norm(title)
    short_norm = norm(title.split(":", 1)[-1])
    for block in blocks:
        text = block["text"].strip()
        if not text:
            continue
        if block["kind"] == "heading":
            heading_norm = norm(text)
            if heading_norm in {title_norm, short_norm}:
                continue
            if "contents" in heading_norm and len(text) < 40:
                continue
            chunks.append(f"## {text}")
            continue
        chunks.append(text)
    return "\n\n".join(chunks).strip()


def nest(entries: list[dict]) -> list[dict]:
    root: list[dict] = []
    stack: list[dict] = []
    for entry in entries:
        node = {**entry, "children": []}
        while stack and stack[-1]["level"] >= node["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            root.append(node)
        stack.append(node)
    return root


def strip_children(nodes: list[dict]) -> list[dict]:
    return [
        {
            "title": node["title"],
            "slug": node["slug"],
            "level": node["level"],
            "children": strip_children(node["children"]),
        }
        for node in nodes
    ]


def save_cover(doc: pymupdf.Document, spec: BookSpec) -> str:
    dest_dir = PUBLIC_BOOKS / spec.id
    dest_dir.mkdir(parents=True, exist_ok=True)
    page = doc[max(0, spec.cover_page - 1)]
    pix = page.get_pixmap(dpi=120, alpha=False)
    if pix.n >= 4:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    path = dest_dir / "cover.jpg"
    pix.save(str(path), jpg_quality=82)
    return f"/books/{spec.id}/cover.jpg"


def extract_book(spec: BookSpec) -> dict:
    pages_dir = CONTENT / spec.id / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for old in pages_dir.glob("*.md"):
        old.unlink()

    doc = pymupdf.open(spec.pdf)
    entries = toc_entries(doc, spec)
    if not entries:
        raise SystemExit(f"no TOC entries for {spec.id}")
    figure_src, figure_clips = extract_figures(doc, spec)
    cover = save_cover(doc, spec)

    lines: list[dict] = []
    start_page = min(entry["page"] for entry in entries)
    last_kept = max(entry["page"] for entry in entries)
    skip = {norm(item) for item in spec.skip_toc}
    end_page = doc.page_count
    for _level, title, page in doc.get_toc():
        if norm(title) in skip and page > last_kept:
            end_page = min(end_page, max(last_kept, page - 1))
    for page_index in range(max(0, start_page - 1), end_page):
        page_recs = collect_lines(doc[page_index], page_index + 1, spec, figure_clips.get(page_index + 1, []))
        lines.extend(reorder_two_column(page_recs, spec))
    lines = attach_kinds(merge_display_titles(lines), spec)
    blocks = insert_figures(merge_split_tables(records_to_blocks(lines, spec)), figure_src)
    blocks = reflow_around_figures(canonicalize_headings(blocks, entries))
    grouped = split_sections(blocks, entries)

    pages_meta = []
    for index, entry in enumerate(entries):
        body = blocks_to_markdown(grouped[index], entry["title"])
        md = (
            "---\n"
            f'title: "{entry["title"].replace(chr(34), chr(39))}"\n'
            f"slug: {entry['slug']}\n"
            f"level: {entry['level']}\n"
            f"page: {entry['page']}\n"
            f"order: {index}\n"
            "---\n\n"
            f"{body}\n"
        )
        path = pages_dir / f"{index:03d}-{entry['slug']}.md"
        path.write_text(md, encoding="utf-8")
        pages_meta.append(
            {
                "title": entry["title"],
                "slug": entry["slug"],
                "level": entry["level"],
                "page": entry["page"],
                "file": path.name,
                "order": index,
            }
        )

    nav = {
        "id": spec.id,
        "title": spec.title,
        "author": spec.author,
        "subtitle": spec.subtitle,
        "year": spec.year,
        "topics": spec.topics,
        "pages": doc.page_count,
        "cover": cover,
        "tree": strip_children(nest(entries)),
        "pagesMeta": pages_meta,
    }
    (CONTENT / spec.id / "nav.json").write_text(json.dumps(nav, indent=2), encoding="utf-8")
    print(f"{spec.id}: {len(pages_meta)} sections, {len(figure_src)} figures")
    return {
        "id": spec.id,
        "title": spec.title,
        "author": spec.author,
        "subtitle": spec.subtitle,
        "year": spec.year,
        "topics": spec.topics,
        "pages": doc.page_count,
        "sections": len(pages_meta),
        "figures": len(figure_src),
        "cover": cover,
        "startSlug": pages_meta[0]["slug"] if pages_meta else "",
        **(
            {"sourceUrl": spec.source_url, "sourceLabel": spec.source_label}
            if spec.source_url
            else {}
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract print PDFs into DeepRead editions.")
    parser.add_argument("--id", help="Extract a single book id from books.json")
    args = parser.parse_args()
    specs = load_specs(args.id)
    extracted = [extract_book(spec) for spec in specs]
    upsert_local_books(extracted)


if __name__ == "__main__":
    main()
