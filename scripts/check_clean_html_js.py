#!/usr/bin/env python3
from pathlib import Path
from bs4 import BeautifulSoup

root = Path(__file__).resolve().parents[1]
html_path = root / "index.html"
text = html_path.read_text(encoding="utf-8")
soup = BeautifulSoup(text, "html.parser")
scripts = soup.find_all("script")
inline = [node.get_text() for node in scripts if not node.get("src")]
if not inline:
    raise SystemExit("No inline script found")
js_path = Path("/tmp/clean_smc_inline.js")
js_path.write_text("\n\n".join(inline), encoding="utf-8")
print(f"scripts={len(scripts)} inline={len(inline)} js_bytes={js_path.stat().st_size}")
print(js_path)
