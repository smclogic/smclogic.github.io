#!/usr/bin/env python3
"""Utilities for storing large wide-row history as GitHub-friendly chunks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_RECOMMENDED_BYTES = 24 * 1024 * 1024


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_year_chunks(root: Path, rows: list[dict[str, Any]]) -> list[str]:
    """Write one JSON array per calendar year and return manifest file names."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        date = str(row.get("Date", ""))[:10]
        year = date[:4] if len(date) >= 4 else "unknown"
        grouped.setdefault(year, []).append(row)

    chunk_dir = root / "data" / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    # Remove obsolete chunk files when a newer import changes the range.
    for old in chunk_dir.glob("*.json"):
        old.unlink()

    files: list[str] = []
    sizes: dict[str, int] = {}
    for year in sorted(grouped):
        filename = f"{year}.json"
        path = chunk_dir / filename
        write_json(path, grouped[year])
        size = path.stat().st_size
        if size >= MAX_RECOMMENDED_BYTES:
            raise ValueError(f"Chunk {filename} is {size} bytes; split it into smaller chunks")
        files.append(filename)
        sizes[filename] = size

    manifest = {
        "format": "SMC Toolkit wide-row JSON chunks",
        "files": files,
        "history_rows": len(rows),
        "first_date": rows[0].get("Date", "") if rows else "",
        "last_date": rows[-1].get("Date", "") if rows else "",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "chunk_bytes": sizes,
    }
    write_json(chunk_dir / "manifest.json", manifest)
    return files
