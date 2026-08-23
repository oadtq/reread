---
title: "Your own books"
slug: your-own-books
level: 2
page: 5
order: 2
---

Extract only books you own or that are licensed for this use. Do not commit reconstructed editions of commercial titles.

## PDF books

1. Create a virtualenv and install `scripts/requirements.txt`.
2. Copy `scripts/books.example.json` to `scripts/books.json`.
3. Point each `pdf` field at a local file and fill in title, author, and a layout `profile`.
4. Run `python scripts/extract-book.py`. Use `--id` to extract one book.

`inference` and `elsevier` are layout profiles for two print styles the extractor already understands. Other PDFs may need a new profile.

## Markdown notes

If you have a repository of notes with one numbered folder per chapter (`01. Rate limiter/README.md`, and so on):

```bash
python scripts/ingest-notes.py ~/src/my-notes \
  --id my-notes \
  --title "My notes" \
  --author "Your name" \
  --topic Distributed \
  --topic Systems
```

The ingest script copies diagrams, converts HTML `<img>` tags to markdown, and writes a generated cover.
