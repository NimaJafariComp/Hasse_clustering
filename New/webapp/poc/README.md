# Browser Worker Proof of Concept

This isolated Phase 0 spike runs the canonical `New/engine.py` and
`New/input_loader.py` in a browser Web Worker through pinned Pyodide
`v314.0.7`. It does not modify the existing web application or replace its
Python HTTP API.

## Run locally

From the repository root:

```bash
python3 -m http.server 8000
```

Open <http://127.0.0.1:8000/New/webapp/poc/>. Click **Run canonical example**.
The first run downloads Pyodide; later runs reuse the worker runtime.

Run the automated Chromium check from the repository root:

```bash
python3 /Users/nimajafari/.agents/skills/webapp-testing/scripts/with_server.py \
  --server "python3 -m http.server 8765 --bind 127.0.0.1" --port 8765 -- \
  python3 New/webapp/poc/validate_poc.py
```

Set `POC_BROWSER=firefox` or `POC_BROWSER=webkit` to run the same harness in
those Playwright engines after installing them.

The expected summary is:

```text
n = 4
|S| = 42
|C| = 109
sources = 2
```

**Run Game V3 reference** loads the repository's 125-row sample CSV and applies
the documented `r=2`, `t=100`, `e1,e2,e5,e6,e11` filter. Its expected summary
is `n=125`, `|S|=126`, `|C|=137`, and one source; use its displayed timing as
the initial realistic-workload benchmark.

Click **Stop worker** during a run to validate worker termination. The next run
creates a fresh worker.

## Phase 0 measurements

The spike displays:

- Pyodide cold-start duration;
- end-to-end total run duration; and
- live engine progress events.

Measured headless results on September 18, 2026 (local development machine):

| Browser engine | Pyodide cold start | Game V3 analysis |
| --- | ---: | ---: |
| Chromium | 878 ms | 36 ms |
| WebKit | 833 ms | 33 ms |

These are feasibility measurements, not public input limits. Browser DevTools
must still be used to record peak memory on representative user devices. The
installed Playwright Firefox runner could not create a temporary profile in the
local environment, so Firefox needs a separate device/browser pass.

Record peak tab memory with each target browser’s developer tools while running
the reference Game V3 input in a later benchmark pass. This spike intentionally
uses the small canonical example so feasibility failures are easy to diagnose.

## Current limitation

The existing server supports synchronous Continue/Abort decisions for engine
runtime warnings. The proof of concept intentionally leaves those warnings
non-blocking because a CPU-bound worker cannot process ordinary messages while
Python is synchronously executing. The planned browser application will replace
them with preflight warnings and measured input limits.
