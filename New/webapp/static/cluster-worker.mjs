import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PYODIDE_INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

let activeRequestId;
let pyodidePromise;
let sourceKey;

function postDiagnostic(message) {
  self.postMessage({ type: "diagnostic", requestId: activeRequestId, message });
}

async function fetchSource(url, name) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load ${name}: HTTP ${response.status}`);
  }
  return response.text();
}

async function loadRuntime(sources) {
  postDiagnostic("Loading Python runtime…");
  const pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX_URL });
  postDiagnostic("Loading clustering engine…");
  const [engineSource, inputLoaderSource] = await Promise.all([
    fetchSource(sources.engine, "engine.py"),
    fetchSource(sources.inputLoader, "input_loader.py"),
  ]);

  pyodide.FS.writeFile("/home/pyodide/engine.py", engineSource);
  pyodide.FS.writeFile("/home/pyodide/input_loader.py", inputLoaderSource);
  pyodide.globals.set("post_progress", (stage, frac, message) => {
    self.postMessage({
      type: "progress",
      requestId: activeRequestId,
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

    # Browser workers cannot synchronously pause for a UI decision while Python
    # is executing. Phase 2 adds preflight warnings and input limits instead.
    result = engine.analyze(
        **params,
        control=engine.Control(progress_cb=emit_progress),
    )
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
  return pyodide;
}

async function runtime(sources) {
  const nextSourceKey = JSON.stringify(sources);
  if (pyodidePromise && sourceKey !== nextSourceKey) {
    throw new Error("The browser worker was initialized with different Python sources.");
  }
  if (!pyodidePromise) {
    sourceKey = nextSourceKey;
    pyodidePromise = loadRuntime(sources);
  }
  return pyodidePromise;
}

self.addEventListener("message", async ({ data }) => {
  if (data?.type !== "run") return;

  activeRequestId = String(data.requestId);
  try {
    const pyodide = await runtime(data.sources);
    pyodide.globals.set("request_json", JSON.stringify(data.request));
    const resultJson = await pyodide.runPythonAsync("analyze_request(request_json)");
    pyodide.globals.delete("request_json");
    self.postMessage({
      type: "result",
      requestId: activeRequestId,
      result: JSON.parse(resultJson),
    });
  } catch (error) {
    self.postMessage({
      type: "error",
      requestId: activeRequestId,
      message: error instanceof Error ? error.message : String(error),
    });
  } finally {
    activeRequestId = undefined;
  }
});
