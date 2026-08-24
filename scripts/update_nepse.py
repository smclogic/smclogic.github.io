#!/usr/bin/env python3
"""Fetch free public NEPSE pages and maintain repository JSON/CSV data.

The output intentionally keeps the existing SMC Chart wide-row contract:

    [{"Date": "YYYY-MM-DD", "Index - Open":  ..., "ADBL-Open": ...}]

That means the current HTML chart parser can consume the generated JSON with
minimal changes. No paid NEPSE API is used.
"""

from __future__ import annotations

import argparse
import csv
import html as html_lib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

MARKET_URL = "https://www.sharesansar.com/market"
PRICE_URL = "https://www.sharesansar.com/today-share-price"
DEFAULT_ROOT = Path(__file__).resolve().parents[1]
NPT = ZoneInfo("Asia/Kathmandu")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/124.0 Safari/537.36 SMC-Toolkit-DataUpdater/1.0"
)

INDEX_METRICS = ("Open", "High", "Low", "Close", "Turnover")
SYMBOL_METRICS = ("Open", "High", "Low", "Close", "Volume")


class DataError(RuntimeError):
    """Raised when a source response is incomplete or cannot be parsed."""


@dataclass(frozen=True)
class SourceSnapshot:
    trading_date: str
    row: dict[str, Any]
    symbol_count: int
    index_count: int


def clean_text(value: str) -> str:
    value = html_lib.unescape(value or "")
    return re.sub(r"\s+", " ", value).strip()


def number(value: Any) -> int | float | str:
    """Convert source values to JSON/CSV-friendly numbers when possible."""
    if value is None:
        return ""
    text = clean_text(str(value)).replace(",", "")
    if not text or text in {"-", "—", "–", "N/A", "NA"}:
        return ""
    text = text.replace("%", "")
    try:
        parsed = float(text)
    except ValueError:
        return text
    if parsed.is_integer():
        return int(parsed)
    return parsed


def fetch(session: requests.Session, url: str, timeout: int) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    if not response.text.strip():
        raise DataError(f"Empty response from {url}")
    return response.text


def row_cells(tr: Any) -> list[str]:
    return [clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]


def table_headers(table: Any) -> list[str]:
    header_rows = table.find_all("tr")
    if not header_rows:
        return []
    # Prefer an explicit thead row; otherwise use the first row.
    thead = table.find("thead")
    candidate = thead.find("tr") if thead else header_rows[0]
    if candidate is None:
        candidate = header_rows[0]
    return row_cells(candidate)


def body_rows(table: Any) -> Iterable[list[str]]:
    body = table.find("tbody") or table
    for tr in body.find_all("tr"):
        cells = row_cells(tr)
        if cells:
            yield cells


def extract_trading_date(market_html: str) -> str:
    match = re.search(r"As\s+of[^0-9]*(\d{4}-\d{2}-\d{2})", market_html, flags=re.I)
    if match:
        return match.group(1)
    # Fallback is only used if the source omits its visible date.
    return datetime.now(NPT).date().isoformat()


def parse_market_page(market_html: str) -> tuple[str, dict[str, dict[str, Any]]]:
    soup = BeautifulSoup(market_html, "html.parser")
    date = extract_trading_date(market_html)
    entities: dict[str, dict[str, Any]] = {}

    for table in soup.find_all("table"):
        headers = [clean_text(h).lower() for h in table_headers(table)]
        if not headers:
            continue
        if headers[0] == "index":
            entity_type = "index"
        elif headers[0] == "sub index":
            entity_type = "subindex"
        else:
            continue

        positions = {name: i for i, name in enumerate(headers)}
        required = {"open", "high", "low", "close", "turnover"}
        if not required.issubset(positions):
            continue
        for cells in body_rows(table):
            if len(cells) <= max(positions.values()):
                continue
            name = clean_text(cells[0])
            if not name:
                continue
            if name == "NEPSE Index":
                name = "Index"
            entity = entities.setdefault(name, {})
            for source_key, output_key in (
                ("open", "Open"),
                ("high", "High"),
                ("low", "Low"),
                ("close", "Close"),
                ("turnover", "Turnover"),
            ):
                entity[output_key] = number(cells[positions[source_key]])

    if not entities:
        raise DataError("No NEPSE index/sub-index rows found on the market page")
    return date, entities


def parse_price_page(price_html: str) -> dict[str, dict[str, Any]]:
    soup = BeautifulSoup(price_html, "html.parser")
    for table in soup.find_all("table"):
        headers = [clean_text(h).lower() for h in table_headers(table)]
        if "symbol" not in headers or not {"open", "high", "low", "close"}.issubset(headers):
            continue
        positions = {name: i for i, name in enumerate(headers)}
        result: dict[str, dict[str, Any]] = {}
        for cells in body_rows(table):
            if len(cells) <= max(positions.values()):
                continue
            symbol = clean_text(cells[positions["symbol"]]).upper()
            if not re.fullmatch(r"[A-Z0-9]+", symbol):
                continue
            record = {
                "Open": number(cells[positions["open"]]),
                "High": number(cells[positions["high"]]),
                "Low": number(cells[positions["low"]]),
                "Close": number(cells[positions["close"]]),
            }
            if "vol" in positions and positions["vol"] < len(cells):
                record["Volume"] = number(cells[positions["vol"]])
            # SMC parsing requires positive OHLC values. Keep rows only when
            # all four prices are valid; a missing volume remains acceptable.
            if all(isinstance(record[k], (int, float)) and record[k] > 0 for k in ("Open", "High", "Low", "Close")):
                result[symbol] = record
        if not result:
            raise DataError("No valid symbol OHLC rows found on the price page")
        return result
    raise DataError("Individual-share price table not found")


def collect_snapshot(session: requests.Session, timeout: int = 30) -> SourceSnapshot:
    market_html = fetch(session, MARKET_URL, timeout)
    price_html = fetch(session, PRICE_URL, timeout)
    trading_date, entities = parse_market_page(market_html)
    symbols = parse_price_page(price_html)

    row: dict[str, Any] = {"Date": trading_date}
    for name in sorted(entities, key=lambda value: (value != "Index", value)):
        for metric in INDEX_METRICS:
            if metric in entities[name] and entities[name][metric] != "":
                row[f"{name} - {metric}"] = entities[name][metric]
    for symbol in sorted(symbols):
        for metric in SYMBOL_METRICS:
            if metric in symbols[symbol] and symbols[symbol][metric] != "":
                row[f"{symbol}-{metric}"] = symbols[symbol][metric]

    if "Index - Open" not in row or "Index - High" not in row or "Index - Low" not in row or "Index - Close" not in row:
        raise DataError("NEPSE Index OHLC is incomplete")
    return SourceSnapshot(
        trading_date=trading_date,
        row=row,
        symbol_count=len(symbols),
        index_count=len(entities),
    )


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, list):
        raise DataError(f"Expected a JSON array in {path}")
    return [row for row in data if isinstance(row, dict) and row.get("Date")]


def merge_row(rows: list[dict[str, Any]], new_row: dict[str, Any]) -> list[dict[str, Any]]:
    by_date = {str(row.get("Date"))[:10]: dict(row) for row in rows if row.get("Date")}
    date = str(new_row["Date"])[:10]
    # Replace the same date so a later run can repair a partial intraday scrape.
    by_date[date] = dict(new_row)
    return [by_date[key] for key in sorted(by_date)]


def ordered_columns(rows: list[dict[str, Any]]) -> list[str]:
    keys = {key for row in rows for key in row.keys()}
    index_keys = sorted((k for k in keys if " - " in k), key=lambda k: (k.rsplit(" - ", 1)[0] != "Index", k))
    symbol_keys = sorted(k for k in keys if " - " not in k and k != "Date")
    return ["Date", *index_keys, *symbol_keys]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in columns} for row in rows)


def write_outputs(root: Path, rows: list[dict[str, Any]], snapshot: SourceSnapshot) -> None:
    data_dir = root / "data"
    history_dir = data_dir / "history"
    columns = ordered_columns(rows)

    write_json(data_dir / "nepse_ohlc.json", rows)
    write_csv(data_dir / "nepse_ohlc.csv", rows, columns)
    write_json(data_dir / "latest.json", snapshot.row)
    write_csv(data_dir / "latest.csv", [snapshot.row], columns)
    write_json(history_dir / f"{snapshot.trading_date}.json", snapshot.row)

    fast_rows = []
    index_columns = [column for column in columns if column == "Date" or " - " in column]
    for row in rows:
        fast_rows.append({column: row[column] for column in index_columns if column in row})
    write_json(data_dir / "nepse_ohlc_fast.json", fast_rows)

    metadata = {
        "source": {"market": MARKET_URL, "prices": PRICE_URL},
        "updated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "latest_trading_date": snapshot.trading_date,
        "history_rows": len(rows),
        "latest_symbol_count": snapshot.symbol_count,
        "latest_index_count": snapshot.index_count,
        "format": "SMC Toolkit wide rows: Date, Index - Open, SYMBOL-Open, ...",
    }
    write_json(data_dir / "manifest.json", metadata)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Repository root")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--min-symbols", type=int, default=100)
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        snapshot = collect_snapshot(session, timeout=args.timeout)
        if snapshot.symbol_count < args.min_symbols:
            raise DataError(
                f"Only {snapshot.symbol_count} valid symbols found; refusing to publish a partial scrape "
                f"(minimum {args.min_symbols})"
            )
        target = args.root / "data" / "nepse_ohlc.json"
        rows = merge_row(load_rows(target), snapshot.row)
        write_outputs(args.root, rows, snapshot)
        print(
            f"Updated {snapshot.trading_date}: {snapshot.index_count} indices, "
            f"{snapshot.symbol_count} symbols, {len(rows)} history rows"
        )
        return 0
    except (requests.RequestException, DataError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
