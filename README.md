# DeepRead

A local web library for technical books you already have the right to read. Point it at a print PDF or a folder of markdown notes and it builds a sectioned, searchable edition with a sidebar, figures, tables, and math.

This repository is the **reader and the extractors**. It does not redistribute copyrighted books. Clones come with one original sample volume (*Using DeepRead*). Editions you extract stay on your machine.

## Requirements

- [Bun](https://bun.sh) 1.3+
- Python 3.11+ (only if you extract books)
- PDFs or notes you are allowed to convert for personal use

## Run the reader

```bash
bun install
bun dev
```

Open [http://localhost:3000](http://localhost:3000). You should see the sample guide.

```bash
bun run lint
bun run build
```

## Add a PDF you own

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements.txt
cp scripts/books.example.json scripts/books.json
```

Edit `scripts/books.json` so each `pdf` path points at a local file, then:

```bash
.venv/bin/python scripts/extract-book.py
# or one book:
.venv/bin/python scripts/extract-book.py --id your-book-id
```

`scripts/books.json` and `content/catalog.local.json` are gitignored. Extracted pages, covers, and figures are gitignored too. Restart the app and the new volume appears next to the sample.

The extractor currently ships two print layout profiles: `inference` and `elsevier`. Other books may need a new profile in `scripts/extract-book.py`.

## Add markdown notes

For a repo with one numbered folder per chapter:

```bash
.venv/bin/python scripts/ingest-notes.py ~/src/my-notes \
  --id my-notes \
  --title "My notes" \
  --author "Your name" \
  --year 2026 \
  --topic Systems \
  --source-url https://example.com/my-notes \
  --source-label "Source notes"
```

## What is in git, and what is not

| Tracked | Local only |
| --- | --- |
| Reader app (`src/`) | Reconstructed book text and figures |
| Extractor scripts | `scripts/books.json` (your PDF paths) |
| Sample guide | `content/catalog.local.json` |
| `content/catalog.json` | `.venv/`, `.next/`, `node_modules/` |

If you fork this project, do not publish reconstructed editions of commercial books.

## License

The DeepRead software is [MIT](LICENSE). Book text, figures, and covers you extract remain under their original copyright. The bundled sample guide is original documentation and is covered by the same MIT license as the code.
