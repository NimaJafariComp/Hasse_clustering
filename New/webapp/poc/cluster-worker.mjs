import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PYODIDE_INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
const ENGINE_URL = new URL("../../engine.py", self.location.href);
const INPUT_LOADER_URL = new URL("../../input_loader.py", self.location.href);

let pyodidePromise;

function now() {
  return performance.now();
}

async function fetchSource(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load ${url.pathname}: HTTP ${response.status}`);
  }
  return response.text();
}

async function loadRuntime() {
  const startedAt = now();
  self.postMessage({ type: "diagnostic", message: "Loading Pyodide runtime…" });
  const pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX_URL });
  self.postMessage({ type: "diagnostic", message: "Loading canonical Python sources…" });
  const [engineSource, inputLoaderSource] = await Promise.all([
    fetchSource(ENGINE_URL),
    fetchSource(INPUT_LOADER_URL),
  ]);

  pyodide.FS.writeFile("/home/pyodide/engine.py", engineSource);
  pyodide.FS.writeFile("/home/pyodide/input_loader.py", inputLoaderSource);
  pyodide.globals.set("post_progress", (stage, frac, message) => {
    self.postMessage({
      type: "progress",
      stage: String(stage),
      frac: Number(frac),
      message: String(message),
    });
  });

  await pyodide.runPythonAsync(`
import json
import sys

sys.path.insert(0, "/home/pyodide")

import engine
from input_loader import parse_sequences_text


def dag_to_json(dag):
    return {
        "edges": sorted([list(e) for e in dag.edges]),
        "vertices": sorted(dag.vertices),
    }


def subset_to_json(subset):
    return [dag_to_json(dag) for dag in engine.canonical_subset_order(subset)]


def emit_progress(stage, frac, message):
    post_progress(stage, frac, message)


def analyze_request(request_json):
    data = json.loads(request_json)
    sequences = data.get("sequences")
    if sequences is None:
        sequences = parse_sequences_text(
            data.get("input_text", ""),
            input_format=data.get("input_format", "auto"),
            sequence_column=data.get("sequence_column", "sequence"),
        )

    params = {
        "sequences": sequences,
        "r": int(data["r"]),
        "t": int(data["t"]),
        "event_filter": set(data["events"]) if data.get("events") else None,
        "detect_bidirectional": bool(data.get("detect_bidirectional", True)),
    }
    if params["r"] < 1 or not 0 <= params["t"] <= 100:
        raise ValueError("r must be >= 1 and t in [0,100]")

    # Phase 0 intentionally makes engine warnings non-blocking. The production
    # browser UI will surface preflight warnings before it starts a worker.
    control = engine.Control(progress_cb=emit_progress)
    result = engine.analyze(**params, control=control)
    return json.dumps({
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
    })
`);
  self.postMessage({ type: "diagnostic", message: "Python engine ready." });

  return { pyodide, coldStartMs: now() - startedAt };
}

async function runtime() {
  if (!pyodidePromise) {
    pyodidePromise = loadRuntime();
  }
  return pyodidePromise;
}

self.addEventListener("message", async ({ data }) => {
  if (data?.type !== "run") return;

  const requestId = String(data.requestId);
  const startedAt = now();
  try {
    const { pyodide, coldStartMs } = await runtime();
    pyodide.globals.set("request_json", JSON.stringify(data.request));
    const resultJson = await pyodide.runPythonAsync("analyze_request(request_json)");
    pyodide.globals.delete("request_json");

    self.postMessage({
      type: "result",
      requestId,
      result: JSON.parse(resultJson),
      metrics: {
        coldStartMs,
        totalRunMs: now() - startedAt,
      },
    });
  } catch (error) {
    self.postMessage({
      type: "error",
      requestId,
      message: error instanceof Error ? error.message : String(error),
    });
  }
});
