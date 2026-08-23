---
title: "The reader"
slug: the-reader
level: 2
page: 3
order: 1
---

The library home lists every volume in the catalog. Open a book and you get three columns on a wide screen: contents, the section, and on-this-page headings.

## Moving around

- The sidebar lists the table of contents. Nested sections expand when you are inside them.
- Search the contents field or press ⌘K / Ctrl+K.
- Previous and next links sit at the end of each section.
- Light and night themes persist in `localStorage`.

## What a book is on disk

Each book is a folder under `content/<id>/` with `nav.json` and a `pages/` directory of markdown files. Covers and figures live under `public/books/<id>/`. The public catalog is `content/catalog.json`. Books you extract locally are merged from `content/catalog.local.json`.
