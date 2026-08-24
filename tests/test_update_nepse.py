import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_nepse import DataError, merge_row, parse_market_page, parse_price_page


MARKET_HTML = """
<div>As of 2026-08-24</div>
<table><thead><tr><th>Index</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Point Change</th><th>% Change</th><th>Turnover</th></tr></thead>
<tbody><tr><td>NEPSE Index</td><td>2,600</td><td>2,650</td><td>2,580</td><td>2,620</td><td>20</td><td>0.7</td><td>4,100,000,000</td></tr></tbody></table>
<table><thead><tr><th>Sub Index</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Point</th><th>% Change</th><th>Turnover</th></tr></thead>
<tbody><tr><td>Banking SubIndex</td><td>1,400</td><td>1,420</td><td>1,390</td><td>1,410</td><td>10</td><td>0.7</td><td>1,000,000,000</td></tr></tbody></table>
"""

PRICE_HTML = """
<table><thead><tr><th>S.No</th><th>Symbol</th><th>Conf.</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>LTP</th><th>VWAP</th><th>Vol</th></tr></thead>
<tbody>
<tr><td>1</td><td>ADBL</td><td>-</td><td>300</td><td>305</td><td>295</td><td>302</td><td>302</td><td>301</td><td>12,345</td></tr>
<tr><td>2</td><td>ACBL</td><td>-</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
</tbody></table>
"""


class UpdateNepseTests(unittest.TestCase):
    def test_parse_market_page_preserves_index_and_subindex_fields(self):
        date, entities = parse_market_page(MARKET_HTML)
        self.assertEqual(date, "2026-08-24")
        self.assertEqual(entities["Index"]["Open"], 2600)
        self.assertEqual(entities["Index"]["Turnover"], 4100000000)
        self.assertEqual(entities["Banking SubIndex"]["Close"], 1410)

    def test_parse_price_page_keeps_valid_symbol_ohlc_and_volume(self):
        symbols = parse_price_page(PRICE_HTML)
        self.assertEqual(list(symbols), ["ADBL"])
        self.assertEqual(
            symbols["ADBL"],
            {"Open": 300, "High": 305, "Low": 295, "Close": 302, "Volume": 12345},
        )

    def test_merge_row_replaces_same_date_and_sorts_history(self):
        old = [
            {"Date": "2026-08-23", "Index - Close": 2600},
            {"Date": "2026-08-24", "Index - Close": 2610},
        ]
        updated = merge_row(old, {"Date": "2026-08-24", "Index - Close": 2620})
        self.assertEqual([row["Date"] for row in updated], ["2026-08-23", "2026-08-24"])
        self.assertEqual(updated[-1]["Index - Close"], 2620)

    def test_invalid_market_page_is_rejected(self):
        with self.assertRaises(DataError):
            parse_market_page("<html><body>No market table</body></html>")


if __name__ == "__main__":
    unittest.main()
