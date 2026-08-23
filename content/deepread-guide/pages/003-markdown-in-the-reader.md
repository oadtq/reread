---
title: "Markdown in the reader"
slug: markdown-in-the-reader
level: 2
page: 7
order: 3
---

Sections are ordinary markdown with YAML front matter (`title`, `slug`, `level`, `page`, `order`). The reader renders GFM tables, fenced code, and KaTeX math using `$$` delimiters.

## Tables

| Token | Role |
| --- | --- |
| `nav.json` | Tree and reading order |
| `pages/*.md` | Section bodies |
| `public/books/<id>/` | Cover and figures |

## Math

Display math is supported:

$$
T_{\text{total}} = T_{\text{queue}} + T_{\text{compute}} + T_{\text{transfer}}
$$

## Figures

Images referenced as `/books/<id>/figures/...` are inlined with captions taken from the alt text.

![A schematic of DeepRead: PDFs and notes flow into a local catalog, then into the web reader.](/books/deepread-guide/figures/library.svg)
