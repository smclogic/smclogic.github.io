# SMC Toolkit — Free NEPSE GitHub Data Pipeline

This project keeps the existing SMC Toolkit visual design and moves the **SMC Chart OHLC data** from Google Apps Script to a free GitHub repository workflow. A Python script collects public daily data from ShareSansar’s market and today-share-price pages [1] [2], validates that the response is complete, writes JSON/CSV files into the repository, and GitHub Actions commits changes automatically after the Nepal market day.

The existing Google Apps Script is retained locally as `apps_script_reference.gs` for reference only. The other toolkit tabs in the copied HTML still contain their original Apps Script URLs; only the embedded SMC Chart data source has been changed to repository JSON placeholders.

## Repository layout

| Path | Purpose |
| --- | --- |
| `scripts/update_nepse.py` | Scrapes the two free public pages, normalizes values, validates completeness, and writes outputs. |
| `data/nepse_ohlc.json` | Full history in the existing wide-row contract used by the SMC Chart. |
| `data/nepse_ohlc.csv` | Same history in CSV form. |
| `data/nepse_ohlc_fast.json` | Compact index/sub-index-only JSON for the chart’s fast first render. |
| `data/latest.json` and `data/latest.csv` | Latest trading-day snapshot. |
| `data/history/YYYY-MM-DD.json` | Immutable-per-date snapshot for easy inspection and backup. |
| `data/manifest.json` | Source URLs, timestamp, row counts, and validation metadata. |
| `.github/workflows/daily-nepse.yml` | Scheduled Sunday–Thursday update job plus manual run support. |
| `smc_toolkit.html` | Copy of the uploaded toolkit with only the SMC Chart source configuration changed. |
| `apps_script_reference.gs` | User-provided Apps Script reference; not required by the GitHub workflow. |

## Data contract

The JSON format intentionally matches the current chart parser. Each history row has a `Date` field and wide columns such as `Index - Open`, `Index - High`, `Index - Low`, `Index - Close`, `Index - Turnover`, `ADBL-Open`, `ADBL-High`, `ADBL-Low`, `ADBL-Close`, and `ADBL-Volume`. The existing chart parser already recognizes this format and converts it into per-instrument OHLC arrays.

The two public source pages are [ShareSansar Market](https://www.sharesansar.com/market) for NEPSE indices/sub-indices and [ShareSansar Today Share Price](https://www.sharesansar.com/today-share-price) for listed-company daily prices [1] [2]. This is **not a licensed NEPSE API** and it may require parser maintenance if the public site changes its layout or access behavior.

## Local run

From the repository root, install the small dependency set and run the updater:

```bash
python3 -m pip install -r requirements.txt
python3 scripts/update_nepse.py
```

The updater refuses to publish a suspiciously small scrape. The default minimum is 100 valid scrips; the workflow uses the same threshold. A same-date rerun replaces that date’s row instead of creating duplicates, which makes manual retries safe.

Run the tests with:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## GitHub setup

Create a GitHub repository and upload the project contents. In the repository settings, the workflow needs permission to write repository contents. The workflow declares `contents: write`; if a repository policy overrides that setting, enable **Settings → Actions → General → Workflow permissions → Read and write permissions**.

Run **Actions → Daily NEPSE OHLC update → Run workflow** once to verify the first GitHub-side scrape. The scheduled job runs at `12:30 UTC`, which is `18:15 Nepal time`, on Sunday through Thursday. GitHub may start scheduled jobs with some delay, so the manual button remains available.

## Connect the HTML to the repository

Open `smc_toolkit.html` and edit the two constants near the SMC Chart configuration:

```js
const GITHUB_DATA_URL = 'https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY/main/data/nepse_ohlc.json';
const GITHUB_FAST_URL = 'https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY/main/data/nepse_ohlc_fast.json';
```

Replace `YOUR_GITHUB_USERNAME` and `YOUR_REPOSITORY` with the real repository owner and name. The HTML can then be served from GitHub Pages or another static host. Raw GitHub URLs are public-read URLs; do not place private credentials in the HTML or JSON files.

## References

[1]: https://www.sharesansar.com/market "ShareSansar Market"
[2]: https://www.sharesansar.com/today-share-price "ShareSansar Today Share Price"
[3]: https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions "GitHub Actions workflow syntax"

## Important scope decision

The current implementation automates the **SMC Chart data only**, as requested. It does not remove or migrate the separate Apps Script endpoints used by SmartMoney Footprint, Broker Accumulation, Stock Scanner, Broker Bias, Risk Plan, or other tabs. Those can be migrated later one tab at a time using the same repository pattern.
