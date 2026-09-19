const EXAMPLE_REQUEST = {
  sequences: [
    ["e1", "e2", "e3"],
    ["e1", "e3", "e2"],
    ["e1", "e2", "e3", "e4"],
    ["e2", "e3"],
  ],
  r: 2,
  t: 60,
  detect_bidirectional: true,
};

const EXPECTED_SUMMARY = { n: 4, num_S: 42, num_C: 109, sources: 2 };
const GAME_V3_EXPECTED_SUMMARY = { n: 125, num_S: 126, num_C: 137, sources: 1 };
const GAME_V3_CSV_URL = new URL(
  "../../../SampleV3GameData/sequence_of_sets_formatted_Won.csv",
  import.meta.url,
);

const runButton = document.querySelector("#run");
const runGameV3Button = document.querySelector("#run-game-v3");
const stopButton = document.querySelector("#stop");
const status = document.querySelector("#status");
const progress = document.querySelector("#progress");
const metrics = document.querySelector("#metrics");
const output = document.querySelector("#output");

let worker;
let activeRequestId;
let requestCounter = 0;
let expectedSummary = EXPECTED_SUMMARY;

function setStatus(message, type = "") {
  status.textContent = message;
  status.dataset.type = type;
}

function setRunning(running) {
  runButton.disabled = running;
  runGameV3Button.disabled = running;
  stopButton.disabled = !running;
}

function summaryMatches(result) {
  const summary = { ...result, sources: result.sources?.length };
  return Object.entries(expectedSummary).every(([key, value]) => summary[key] === value);
}

function startWorker() {
  worker = new Worker("./cluster-worker.mjs", { type: "module" });
  worker.addEventListener("message", ({ data }) => {
    if (data?.type === "diagnostic" && activeRequestId) {
      progress.textContent = data.message;
      return;
    }
    if (data?.type === "progress" && activeRequestId) {
      const percent = Math.round(data.frac * 100);
      progress.textContent = `${percent}% — ${data.stage}: ${data.message}`;
      return;
    }
    if (data?.requestId !== activeRequestId) return;

    if (data.type === "result") {
      const passed = summaryMatches(data.result);
      setStatus(
        passed ? "Browser result matches the native reference summary." : "Result completed, but the reference summary did not match.",
        passed ? "success" : "error",
      );
      metrics.textContent = `Pyodide cold start: ${Math.round(data.metrics.coldStartMs)} ms | total run: ${Math.round(data.metrics.totalRunMs)} ms`;
      output.textContent = JSON.stringify(data.result, null, 2);
      activeRequestId = undefined;
      setRunning(false);
    } else if (data.type === "error") {
      setStatus(`Worker error: ${data.message}`, "error");
      activeRequestId = undefined;
      setRunning(false);
    }
  });
  worker.addEventListener("error", (event) => {
    setStatus(`Worker failed: ${event.message}`, "error");
    activeRequestId = undefined;
    setRunning(false);
  });
}

function runRequest(request, nextExpectedSummary, label) {
  if (!worker) startWorker();
  activeRequestId = `poc-${++requestCounter}`;
  expectedSummary = nextExpectedSummary;
  progress.textContent = "Starting Pyodide worker…";
  metrics.textContent = "";
  output.textContent = "";
  setStatus(`Running ${label} in this browser…`);
  setRunning(true);
  worker.postMessage({ type: "run", requestId: activeRequestId, request });
}

runButton.addEventListener("click", () => {
  runRequest(EXAMPLE_REQUEST, EXPECTED_SUMMARY, "the canonical Python engine");
});

runGameV3Button.addEventListener("click", async () => {
  setRunning(true);
  setStatus("Loading the Game V3 reference CSV…");
  try {
    const response = await fetch(GAME_V3_CSV_URL);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    runRequest(
      {
        input_text: await response.text(),
        input_format: "csv",
        sequence_column: "sequence",
        r: 2,
        t: 100,
        events: ["e1", "e2", "e5", "e6", "e11"],
        detect_bidirectional: true,
      },
      GAME_V3_EXPECTED_SUMMARY,
      "the Game V3 reference analysis",
    );
  } catch (error) {
    setStatus(`Could not load the Game V3 reference CSV: ${error.message}`, "error");
    setRunning(false);
  }
});

stopButton.addEventListener("click", () => {
  worker?.terminate();
  worker = undefined;
  activeRequestId = undefined;
  progress.textContent = "";
  setStatus("Stopped by terminating the browser worker.", "success");
  setRunning(false);
});
