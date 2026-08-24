# NEPSE free-source findings

Date checked: 2026-08-24

## ShareSansar index history
URL: https://www.sharesansar.com/index-history-data

The public page is titled “Index History Data” and exposes a table with Open, High, Low, Close, Change, Per Change (%), Turnover, and Date columns. The page includes selectable index and date-range controls, indicating that it is suitable for NEPSE index daily OHLC collection if the public request behind the table can be replicated or the existing Apps Script already accesses it.

## ShareSansar individual share price
URL: https://www.sharesansar.com/today-share-price

The public page is titled “Today Share Price” and visibly exposes individual scrip rows with Symbol, Open, High, Low, Close, LTP, Prev. Close, VWAP, Volume, Turnover, Transactions, Difference, and Difference % fields. It also exposes sector and date controls. This is a practical free web source for daily scrip OHLC, subject to the site’s public access behavior, terms, and possible HTML/request changes.

## Integration implication

The user has a working Google Apps Script scraper. Prefer reusing that collector and only adding a handoff layer to Google Sheet/JSON or a web-app `doGet()` endpoint. Python in GitHub Actions should validate and archive the output rather than reimplementing the scraper unless the user provides the current Apps Script and its endpoint logic.
