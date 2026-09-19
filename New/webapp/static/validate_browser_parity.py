"""Compare canonical native payloads against the Pyodide browser worker.

Run from the repository root:

python3 /Users/nimajafari/.agents/skills/webapp-testing/scripts/with_server.py \
  --server "cd New && python3 webapp/server.py --port 8765" --port 8765 -- \
  python3 New/webapp/static/validate_browser_parity.py

The only browser network requests are static assets/Pyodide runtime GETs. Test
inputs are passed to the Worker with postMessage and are never sent to an API.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[3]
STATIC_DIR = Path(__file__).resolve().parent
BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8765")
sys.path.insert(0, str(ROOT / "New"))

import engine  # noqa: E402
from input_loader import parse_sequences_text  # noqa: E402


SOURCES = {"engine": "../python/engine.py", "inputLoader": "../python/input_loader.py"}


def dag_to_json(dag: Any) -> dict[str, list[Any]]:
    return {"edges": sorted([list(edge) for edge in dag.edges]), "vertices": sorted(dag.vertices)}


def subset_to_json(subset: Any) -> list[dict[str, list[Any]]]:
    return [dag_to_json(dag) for dag in engine.canonical_subset_order(subset)]


def native_payload(request: dict[str, Any]) -> dict[str, Any]:
    """Mirror the small Python adapter embedded in cluster-worker.mjs."""
    sequences = request.get("sequences")
    if sequences is None:
        sequences = parse_sequences_text(
            request.get("input_text", ""),
            input_format=request.get("input_format", "auto"),
            sequence_column=request.get("sequence_column", "sequence"),
        )
    params = {
        "sequences": sequences,
        "r": int(request["r"]),
        "t": int(request["t"]),
        "event_filter": set(request["events"]) if request.get("events") else None,
        "detect_bidirectional": bool(request.get("detect_bidirectional", True)),
    }
    if params["r"] < 1 or not 0 <= params["t"] <= 100:
        raise ValueError("r must be >= 1 and t in [0,100]")
    result = engine.analyze(**params)
    return {
        "n": result["n"],
        "n_loaded": result["n_loaded"],
        "n_empty": result["n_empty"],
        "num_S": len(result["S"]),
        "num_C": len(result["C"]),
        "sources": [subset_to_json(subset) for subset in result["sources"]],
        "sequences": result["valid_sequences"],
        "original_sequences": params["sequences"],
        "sequence_indices": result["valid_indices"],
        "source_members": result["source_members"],
    }


def load_cases() -> list[dict[str, Any]]:
    fixtures = json.loads((STATIC_DIR / "browser-fixtures.json").read_text())
    cases = fixtures["cases"]
    for case in cases:
        if "inputFile" in case:
            request = case["request"] = dict(case["request"])
            request["input_text"] = (STATIC_DIR / case["inputFile"]).resolve().read_text()
    return cases


def run_worker_cases(page: Any, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return page.evaluate(
        """async ({ requests, sources }) => new Promise((resolve) => {
          const worker = new Worker('/static/cluster-worker.mjs', { type: 'module' });
          const results = [];
          let index = 0;
          let requestId;
          const next = () => {
            if (index === requests.length) {
              worker.terminate();
              resolve(results);
              return;
            }
            requestId = `parity-${index}-${crypto.randomUUID()}`;
            worker.postMessage({ type: 'run', requestId, request: requests[index], sources });
          };
          worker.onmessage = ({ data }) => {
            if (data?.requestId !== requestId || !['result', 'error'].includes(data.type)) return;
            results.push(data.type === 'result'
              ? { kind: 'result', value: data.result }
              : { kind: 'error', message: data.message });
            index += 1;
            next();
          };
          worker.onerror = (event) => {
            worker.terminate();
            resolve([...results, { kind: 'error', message: event.message || 'worker error' }]);
          };
          next();
        })""",
        {"requests": requests, "sources": SOURCES},
    )


def verify_stop_then_restart(page: Any) -> None:
    """Terminate an active exact search, then prove the next UI run wins."""
    page.goto(BASE_URL, wait_until="networkidle", timeout=30_000)
    page.get_by_role("button", name="Run", exact=True).click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Done.'", timeout=10_000)

    expensive = [[f"e{i}" for i in range(1, 12)]]
    page.locator("#sequences").fill(json.dumps(expensive))
    page.locator("#input-format").select_option("json")
    page.locator("#events").fill("")
    page.locator("#r").fill("1")
    page.locator("#t").fill("100")
    page.get_by_role("button", name="Run", exact=True).click()
    page.wait_for_selector("#modal:not(.hidden)", timeout=5_000)
    page.get_by_role("button", name="Continue", exact=True).click()
    page.wait_for_timeout(50)
    assert page.locator("#stop").is_enabled(), "The expensive worker did not start."
    page.get_by_role("button", name="Stop", exact=True).click()
    assert page.locator("#status").text_content() == "Stopped by user."

    page.locator("#sequences").fill(json.dumps([["e1", "e2", "e3"], ["e1", "e3", "e2"], ["e1", "e2", "e3", "e4"], ["e2", "e3"]]))
    page.locator("#events").fill("e1,e2,e3")
    page.locator("#r").fill("2")
    page.locator("#t").fill("60")
    page.get_by_role("button", name="Run", exact=True).click()
    page.wait_for_selector("#modal:not(.hidden)", timeout=5_000)
    page.get_by_role("button", name="Continue", exact=True).click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Done.'", timeout=10_000)
    expected = native_payload({
        "sequences": [["e1", "e2", "e3"], ["e1", "e3", "e2"], ["e1", "e2", "e3", "e4"], ["e2", "e3"]],
        "r": 2,
        "t": 60,
        "events": ["e1", "e2", "e3"],
        "detect_bidirectional": True,
    })
    summary = page.locator("#summary").inner_text().upper()
    assert f"VALID ROWS N\n{expected['n']}" in summary
    assert f"QUALIFYING SUBSETS |C|\n{expected['num_C']}" in summary


def main() -> None:
    cases = load_cases()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        requests: list[tuple[str, str]] = []
        page.on("request", lambda req: requests.append((req.method, req.url)))
        page.goto(BASE_URL, wait_until="networkidle", timeout=30_000)

        actual_cases = run_worker_cases(page, [case["request"] for case in cases])
        assert len(actual_cases) == len(cases), actual_cases
        for case, actual in zip(cases, actual_cases, strict=True):
            native_error = None
            try:
                expected = native_payload(case["request"])
            except Exception as error:  # the invalid-input fixture is intentional
                native_error = str(error)
                expected = None
            if native_error is not None:
                assert actual["kind"] == "error", (case["id"], actual)
                assert case["expectError"] in native_error and case["expectError"] in actual["message"], (case["id"], native_error, actual)
            else:
                assert actual == {"kind": "result", "value": expected}, case["id"]
            print(f"Parity fixture passed: {case['id']}", flush=True)

        print("Testing Stop followed by a fresh run…", flush=True)
        verify_stop_then_restart(page)
        assert not any(method != "GET" for method, _ in requests), requests
        assert not any("/api/" in url for _, url in requests), requests
        browser.close()

    print(f"Browser/native parity passed for {len(cases)} fixtures, including Game V3 and stop/restart.")


if __name__ == "__main__":
    main()
