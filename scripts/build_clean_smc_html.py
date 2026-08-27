#!/usr/bin/env python3
"""Extract the embedded SMC Chart app into a clean GitHub Pages HTML file."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "smc_toolkit_original.html"
TARGET = ROOT / "index.html"


def extract_app(source: str) -> str:
    marker = "  apps[10] = `"
    start = source.find(marker)
    if start < 0:
        raise RuntimeError("Could not find apps[10] SMC Chart template")
    start += len(marker)
    end_marker = "</body></html>`;"
    end = source.find(end_marker, start)
    if end < 0:
        raise RuntimeError("Could not find the end of the SMC Chart template")
    document = source[start:end] + "</body></html>"

    # The extracted text was originally nested in a JavaScript template string.
    # Restore escapes that were needed only by the outer wrapper.
    document = document.replace("<\\/script>", "</script>")
    document = document.replace("\\${", "${")
    document = document.replace("\\`", "`")
    # The outer wrapper doubled apostrophe escapes inside inner JavaScript strings.
    document = document.replace("\\\\'", "\\'")
    # Restore all other doubled backslashes from the nested template literal.
    document = document.replace("\\\\", "\\")

    # Remove analytics from the standalone page; they are not required for the chart.
    document = re.sub(
        r"\s*<!-- Google tag \(gtag\.js\) -->\s*<script async src=\"https://www\.googletagmanager\.com/gtag/js\?id=[^\"]+\"></script>\s*<script>.*?</script>",
        "",
        document,
        flags=re.S,
    )

    # Use repository-relative files so the same HTML works on GitHub Pages,
    # localhost, and a downloaded static copy without placeholders or APIs.
    data_config = (
        "const GITHUB_DATA_URL = './data/nepse_ohlc.json';\n"
        "const GITHUB_FAST_URL = './data/nepse_ohlc_fast.json';\n"
        "const CHUNK_MANIFEST_URL = './data/chunks/manifest.json';\n"
        "const DATA_URL = CHUNK_MANIFEST_URL;"
    )
    document, replacements = re.subn(
        r"const SHEET_URL = '[^']+';",
        data_config,
        document,
        count=1,
    )
    if replacements != 1:
        raise RuntimeError("Could not replace the SMC Chart data URL")
    document = document.replace(
        "SHEET_URL + '?type=fast'",
        "GITHUB_FAST_URL",
    )
    document = document.replace("SHEET_URL", "DATA_URL")
    chunk_loader = """
async function fetchChunkedRows() {
    const manifestResponse = await fetchWithTimeout(CHUNK_MANIFEST_URL + '?v=' + Date.now(), { method: 'GET', redirect: 'follow', cache: 'no-store' }, 10000);
    if (!manifestResponse.ok) throw new Error('Chunk manifest request failed: ' + manifestResponse.status);
    const manifest = await manifestResponse.json();
    if (!manifest || !Array.isArray(manifest.files) || !manifest.files.length) throw new Error('No history chunks found in repository');
    const parts = await Promise.all(manifest.files.map(async (file) => {
        const response = await fetchWithTimeout('./data/chunks/' + encodeURIComponent(file) + '?v=' + Date.now(), { method: 'GET', redirect: 'follow', cache: 'no-store' }, 20000);
        if (!response.ok) throw new Error('History chunk request failed: ' + file + ' (' + response.status + ')');
        const rows = await response.json();
        return Array.isArray(rows) ? rows : [];
    }));
    return parts.flat().sort((a, b) => String(a.Date || '').localeCompare(String(b.Date || '')));
}
"""
    document = document.replace("async function loadData() {", chunk_loader + "\nasync function loadData() {", 1)
    document = document.replace("Apps Script endpoint", "repository data files")
    document = document.replace("from the Apps Script output", "from the repository JSON output")
    document = document.replace("Google Sheets may return formatted strings", "The source may return formatted strings")
    document = document.replace("Ensure the Apps Script is deployed with access set to \"Anyone\".", "Ensure the repository data files are uploaded and accessible, then refresh.")
    document = document.replace("const CACHE_KEY_FAST = 'nepse_chart_cache_fast';", "const CACHE_KEY_FAST = 'nepse_chart_cache_fast_github_v2';")
    document = document.replace("const CACHE_KEY_FULL = 'nepse_chart_cache_full';", "const CACHE_KEY_FULL = 'nepse_chart_cache_full_github_v2';")
    document = document.replace("const IDB_NAME       = 'nepse_chart_idb';", "const IDB_NAME       = 'nepse_chart_idb_github_v2';")
    document = document.replace(
        "fetchWithTimeout(GITHUB_FAST_URL, { method: 'GET', redirect: 'follow' }, 10000)",
        "fetchWithTimeout(GITHUB_FAST_URL + '?v=' + Date.now(), { method: 'GET', redirect: 'follow', cache: 'no-store' }, 10000)",
    )
    document = document.replace(
        "fetchWithTimeout(DATA_URL, { method: 'GET', redirect: 'follow' }, 14000)",
        "fetchChunkedRows()",
    )

    # The final document must not contain an Apps Script or Google Sheets data call.
    forbidden = ["script.google.com", "googleusercontent.com", "APPS_SCRIPT_URL", "GAS_URL", "SCRIPT_URL"]
    remaining = [token for token in forbidden if token in document]
    if remaining:
        raise RuntimeError(f"Forbidden external data references remain: {remaining}")
    return document


def main() -> None:
    document = extract_app(SOURCE.read_text(encoding="utf-8"))
    TARGET.write_text(document, encoding="utf-8")
    print(f"Wrote {TARGET} ({len(document):,} bytes)")


if __name__ == "__main__":
    main()
