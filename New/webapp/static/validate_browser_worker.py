"""Exercise the existing UI with browser-side Pyodide computation.

Run from the repository root:

python3 /Users/nimajafari/.agents/skills/webapp-testing/scripts/with_server.py \
  --server "cd New && python3 webapp/server.py --port 8765" --port 8765 -- \
  python3 New/webapp/static/validate_browser_worker.py
"""

from __future__ import annotations

import os
import re

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8765")


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        requests: list[str] = []
        console_errors: list[str] = []
        page.on("request", lambda request: requests.append(request.url))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )

        page.goto(BASE_URL, wait_until="networkidle", timeout=30_000)
        page.get_by_role("button", name="Run", exact=True).click()
        page.wait_for_function(
            "['Done.', 'Stopped by user.'].includes(document.querySelector('#status').textContent) || document.querySelector('#status').textContent.startsWith('Halted:') || document.querySelector('#status').textContent.startsWith('Browser worker failed:')",
            timeout=30_000,
        )
        assert page.locator("#status").text_content() == "Done.", {
            "status": page.locator("#status").text_content(),
            "console_errors": console_errors,
        }

        summary = page.locator("#summary").inner_text().upper()
        assert "VALID ROWS N\n4" in summary, summary
        assert "DISTINCT DAGS |S|\n42" in summary, summary
        assert "QUALIFYING SUBSETS |C|\n6" in summary, summary
        assert "SOURCES\n1" in summary, summary

        page.get_by_role("button", name="Refine ▸").first.click()
        page.get_by_role("button", name=re.compile(r"Run on \d+ rows")).click()
        page.wait_for_function(
            "document.querySelector('#rf-status-1').textContent === 'Done.'",
            timeout=180_000,
        )
        assert not any("/api/" in url for url in requests), requests
        assert any("/python/engine.py" in url for url in requests), requests
        assert not console_errors, console_errors

        page.locator("#r").fill("4")
        page.get_by_role("button", name="Run", exact=True).click()
        page.wait_for_selector("#modal:not(.hidden)")
        assert "r = 4" in (page.locator("#modal-msg").text_content() or "")
        page.get_by_role("button", name="Abort", exact=True).click()
        assert "cancelled before it started" in (page.locator("#status").text_content() or "")
        browser.close()

    print("Existing UI completed in Chromium with browser-side Python computation.")


if __name__ == "__main__":
    main()
