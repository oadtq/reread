# Contributing

Thanks for considering a patch. DeepRead is a reader plus extractors — please keep reconstructed books out of git.

## Development

```bash
bun install
bun dev
bun run lint
bun run build
```

Python extractors:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements.txt
```

## Pull requests

- Prefer small, focused changes (reader UI, an extractor profile, or docs).
- Do not commit PDFs, extracted markdown, covers, figures, `scripts/books.json`, or `content/catalog.local.json`.
- Do not add copyrighted book text, even as “fixtures.”
- Match the existing TypeScript / Python style. Keep comments rare and only when they explain a non-obvious rule.

## Extractor profiles

New PDF layouts belong in `scripts/extract-book.py` as a named `profile`, plus an example entry in `scripts/books.example.json` that uses a placeholder path (`~/Documents/books/example.pdf`), not a personal Downloads path.
