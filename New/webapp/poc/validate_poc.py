"""Validate the Pyodide browser-worker proof of concept with Playwright.

Run with the repository served at http://127.0.0.1:8765, for example via:

python3 /Users/nimajafari/.agents/skills/webapp-testing/scripts/with_server.py \
  --server "python3 -m http.server 8765 --bind 127.0.0.1" --port 8765 -- \
  python3 New/webapp/poc/validate_poc.py
"""

from __future__ import annotations

import json
import os
from time import monotonic

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("POC_BASE_URL", "http://127.0.0.1:8765")
POC_URL = f"{BASE_URL}/New/webapp/poc/"
BROWSER_NAME = os.environ.get("POC_BROWSER", "chromium")
EXPECTED = {"n": 4, "num_S": 42, "num_C": 109, "sources": 2}
GAME_V3_EXPECTED = {"n": 125, "num_S": 126, "num_C": 137, "sources": 1}


def main() -> None:
    with sync_playwright() as playwright:
        try:
            browser_type = getattr(playwright, BROWSER_NAME)
        except AttributeError as error:
            raise ValueError(f"unsupported Playwright browser: {BROWSER_NAME}") from error
        browser = browser_type.launch(headless=True)
        page = browser.new_page()
        console_errors: list[str] = []
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )

        page.goto(POC_URL, wait_until="networkidle", timeout=30_000)
        page.get_by_role("button", name="Run canonical example").click()
        stop_started_at = monotonic()
        page.get_by_role("button", name="Stop worker").click()
        page.wait_for_function(
            "document.querySelector('#status').textContent.includes('Stopped by terminating')",
            timeout=5_000,
        )
        assert monotonic() - stop_started_at < 5, "Worker stop was unexpectedly slow"

        page.get_by_role("button", name="Run canonical example").click()
        page.wait_for_function(
            "!document.querySelector('#run').disabled",
            timeout=60_000,
        )

        status = page.locator("#status").text_content() or ""
        result = json.loads(page.locator("#output").text_content() or "{}")
        assert "matches the native reference summary" in status, {
            "status": status,
            "output": result,
            "console_errors": console_errors,
        }
        summary = {**result, "sources": len(result["sources"])}
        assert {key: summary[key] for key in EXPECTED} == EXPECTED, result
        example_metrics = page.locator("#metrics").text_content() or ""
        assert "Pyodide cold start:" in example_metrics

        page.get_by_role("button", name="Run Game V3 reference").click()
        page.wait_for_function(
            "!document.querySelector('#run-game-v3').disabled",
            timeout=180_000,
        )
        game_status = page.locator("#status").text_content() or ""
        game_result = json.loads(page.locator("#output").text_content() or "{}")
        game_metrics = page.locator("#metrics").text_content() or ""
        game_summary = {**game_result, "sources": len(game_result["sources"])}
        assert "matches the native reference summary" in game_status, game_status
        assert {key: game_summary[key] for key in GAME_V3_EXPECTED} == GAME_V3_EXPECTED, game_result
        assert not console_errors, console_errors
        browser.close()

    print(
        f"Pyodide worker proof of concept passed in {BROWSER_NAME}. "
        f"Example: {example_metrics}. Game V3: {game_metrics}."
    )


if __name__ == "__main__":
    main()
