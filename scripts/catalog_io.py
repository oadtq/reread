"""Read and write the gitignored local catalog."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
LOCAL_CATALOG = CONTENT / "catalog.local.json"


def upsert_local_books(entries: list[dict]) -> None:
    CONTENT.mkdir(parents=True, exist_ok=True)
    catalog: dict = {"name": "DeepRead", "kicker": "Technical library", "books": []}
    if LOCAL_CATALOG.exists():
        catalog = json.loads(LOCAL_CATALOG.read_text(encoding="utf-8"))
        if not isinstance(catalog.get("books"), list):
            catalog["books"] = []
    incoming = {entry["id"] for entry in entries}
    extras = [book for book in catalog.get("books", []) if book.get("id") not in incoming]
    catalog["books"] = [*entries, *extras]
    LOCAL_CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"local catalog: {len(catalog['books'])} books")
