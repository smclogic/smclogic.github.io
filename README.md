# SMC Toolkit — Clean GitHub-only Website

This is the clean static version of the SMC Chart extracted from the existing SMC Toolkit. The chart UI, controls, SMC calculations, indicators, screeners, overlays, replay tools, responsive layout, and theme behavior are preserved. The old Google Apps Script data dependency has been removed from this clean page.

The site is designed for the `smclogic.github.io` repository. `index.html` reads data from repository-relative files, so no username, repository placeholder, Google Sheet URL, credential, or paid NEPSE API is required.

## Repository layout

| Path | Purpose |
| --- | --- |
| `index.html` | Clean standalone SMC Chart website with the existing chart UI and client-side logic. |
| `data/chunks/YYYY.json` | Yearly historical wide-format OHLC chunks; each file stays below GitHub’s browser upload limit. |
| `data/chunks/manifest.json` | List of yearly chunks and their date/size metadata. |
| `data/nepse_ohlc_fast.json` | Historical index/sub-index data for quick first rendering. |
| `data/latest.json` and `data/latest.csv` | Latest trading-day snapshot. |
| `data/nepse_ohlc.csv` | Full history in CSV form. |
| `data/history/YYYY-MM-DD.json` | Per-date archive snapshot. |
| `data/manifest.json` | Source, timestamp, row-count, and validation metadata. |
| `scripts/update_nepse.py` | Free public-page scraper and daily JSON/CSV exporter. |
| `scripts/import_history_xlsx.py` | One-time Google Sheets XLSX history importer. |
| `.github/workflows/daily-nepse.yml` | Manual and scheduled GitHub Actions updater. |
| `tests/test_update_nepse.py` | Offline parser and merge tests. |

## Historical data already imported

The uploaded Google Sheets workbook was converted into the repository format. It contains one `NepseComplete` sheet, 2,216 dated rows from `2017-01-01` through `2026-08-24`, 2,350 data columns, 18 index/sub-index groups, and approximately 470 stock instruments across the available history. The importer preserves sparse historical rows and does not discard a date merely because some instruments did not yet exist.

The chart reads `data/chunks/manifest.json`, fetches all yearly chunks, and combines them in the browser. The fast file is also historical, but contains only index/sub-index columns so the NEPSE chart can render quickly. The yearly chunks are used to populate stock selectors and individual instrument history.

## Data source and daily update

The historical seed comes from the user’s Google Sheets XLSX export. Future daily rows are collected from public tables on [ShareSansar Market][1] for NEPSE indices and sub-indices, and [ShareSansar Today Share Price][2] for listed-company daily OHLC and volume. This is a free public-page collection method, not a licensed NEPSE API. If a source website changes its table layout or access behavior, the parser may need maintenance.

The daily updater merges each fresh row field-by-field into the matching date. It does not replace the entire historical row, so a partial live response cannot erase older OHLC/volume fields imported from the workbook. If the source returns too few symbols or malformed data, the workflow fails before publishing a partial replacement.

## One-time Google Sheet import

The importer is already run for the supplied workbook. To repeat the process with a newer XLSX export, place the file in the project directory and run:

```bash
python3 scripts/import_history_xlsx.py path/to/your-export.xlsx
```

The importer expects the first worksheet row to contain the wide headers used by the chart, such as `Date`, `Index - Open`, `Index - High`, `Index - Low`, `Index - Close`, `Index - Turnover`, and `ADBL-Open`. It merges dates, removes empty cells, normalizes Excel dates to `YYYY-MM-DD`, rejects duplicate headers, writes yearly JSON chunks, and rewrites the repository CSV files.

## GitHub setup

Upload the complete contents of this folder to the root of the `smclogic.github.io` repository on the `main` branch. The hidden workflow path must be created exactly as `.github/workflows/daily-nepse.yml`; do not place the YAML file at the repository root.

In **Settings → Actions → General**, make sure workflow permissions allow **Read and write permissions** for repository contents. Then open **Actions → Daily NEPSE OHLC update → Run workflow → Run workflow**. A successful run will update only the `data/` files. It will not replace or modify unrelated website files.

The scheduled job runs at `12:30 UTC`, which is `18:15 Nepal time`, Sunday through Thursday. GitHub may delay scheduled jobs, so the manual run remains available.

## Run locally

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m http.server 8000
```

Then open `http://localhost:8000/`. Opening `index.html` directly with `file://` can be blocked by browser CORS rules. The local chart should load the chunk manifest and yearly repository JSON files, then display multiple years of candles.

## What was removed

The clean `index.html` contains no `script.google.com`, Google Sheets, Apps Script endpoint, or paid API data call. The other original toolkit tabs were not copied into this clean page because their independent features depended on separate Apps Script backends and data contracts. This clean version intentionally focuses on the requested SMC Chart and GitHub-hosted NEPSE OHLC data.

## References

[1]: https://www.sharesansar.com/market "ShareSansar Market"
[2]: https://www.sharesansar.com/today-share-price "ShareSansar Today Share Price"
[3]: https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions "GitHub Actions workflow syntax"
