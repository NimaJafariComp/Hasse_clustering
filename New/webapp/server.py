"""
Hasse Sequence Clustering — web app (dependency-free, Python stdlib only).

Runs under CPython or PyPy with no pip installs. Serves a single-page UI and a
small JSON API that runs the analysis in a background thread, streaming progress
and supporting a stop button and runtime-warning "continue" prompts.

Start:
  python webapp/server.py            # serves http://127.0.0.1:8000
  python webapp/server.py --port 9000
"""

import argparse
import json
import os
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Import the engine from the parent folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import engine  # noqa: E402
from input_loader import parse_sequences_text  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #

def dag_to_json(dag):
    return {
        "edges": sorted([list(e) for e in dag.edges]),
        "vertices": sorted(dag.vertices),
    }


def subset_to_json(subset):
    # Same canonical order as engine.source_membership, so the per-DAG member
    # lists in the payload line up with the serialized DAGs.
    return [dag_to_json(d) for d in engine.canonical_subset_order(subset)]


# --------------------------------------------------------------------------- #
# Job management
# --------------------------------------------------------------------------- #

class Job:
    def __init__(self, params):
        self.id = uuid.uuid4().hex[:12]
        self.params = params
        self.lock = threading.Lock()
        self.state = "running"        # running | awaiting | done | stopped | error
        self.stage = "start"
        self.frac = 0.0
        self.message = "Starting..."
        self.warning = None           # message string when state == awaiting
        self.result = None
        self.error = None
        self._gate = threading.Event()
        self._continue = False
        self.control = engine.Control(progress_cb=self._on_progress,
                                      warn_cb=self._on_warn)

    def _on_progress(self, stage, frac, message):
        with self.lock:
            self.stage = stage
            self.frac = frac
            self.message = message

    def _on_warn(self, message):
        # Called in the worker thread; block until the user decides.
        with self.lock:
            self.state = "awaiting"
            self.warning = message
        self._gate.clear()
        self._gate.wait()             # released by resume()
        with self.lock:
            self.state = "running"
            self.warning = None
        return self._continue

    def resume(self, cont: bool):
        self._continue = cont
        self._gate.set()

    def request_stop(self):
        self.control.request_stop()
        # If we're blocked on a warning gate, release it with abort.
        self._continue = False
        self._gate.set()

    def snapshot(self):
        with self.lock:
            data = {
                "id": self.id,
                "state": self.state,
                "stage": self.stage,
                "frac": self.frac,
                "message": self.message,
                "warning": self.warning,
                "error": self.error,
            }
            if self.state == "done" and self.result is not None:
                data["result"] = self.result
            return data


class JobManager:
    def __init__(self):
        self.jobs = {}
        self.lock = threading.Lock()

    def start(self, params):
        job = Job(params)
        with self.lock:
            self.jobs[job.id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job.id

    def get(self, job_id):
        with self.lock:
            return self.jobs.get(job_id)

    def _run(self, job):
        p = job.params
        try:
            res = engine.analyze(
                p["sequences"], r=p["r"], t=p["t"],
                event_filter=p.get("event_filter"),
                detect_bidirectional=p.get("detect_bidirectional", True),
                control=job.control,
            )
            payload = {
                "n": res["n"],
                "n_loaded": res["n_loaded"],
                "n_empty": res["n_empty"],
                "num_S": len(res["S"]),
                "num_C": len(res["C"]),
                "sources": [subset_to_json(s) for s in res["sources"]],
                "sequences": res["valid_sequences"],
                "original_sequences": p["sequences"],
                "sequence_indices": res["valid_indices"],
                "source_members": res["source_members"],
            }
            with job.lock:
                job.result = payload
                job.state = "done"
                job.frac = 1.0
                job.message = "Complete"
        except engine.Cancelled:
            with job.lock:
                job.state = "stopped"
                job.message = "Stopped by user"
        except ValueError as e:
            with job.lock:
                job.state = "error"
                job.error = str(e)
                job.message = "Halted"
        except Exception as e:  # pragma: no cover - defensive
            with job.lock:
                job.state = "error"
                job.error = f"{type(e).__name__}: {e}"
                job.message = "Error"


MANAGER = JobManager()


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw or b"{}")

    def do_GET(self):
        path = self.path.split("?", 1)[0]  # ignore query string for routing
        if path in ("/", "/index.html"):
            self._send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/static/app.js":
            self._send_file(os.path.join(STATIC_DIR, "app.js"), "application/javascript")
        elif path == "/static/style.css":
            self._send_file(os.path.join(STATIC_DIR, "style.css"), "text/css")
        elif path == "/api/status":
            job_id = self.path.split("job=", 1)[-1] if "job=" in self.path else ""
            job = MANAGER.get(job_id)
            if not job:
                self._send_json({"error": "unknown job"}, 404)
            else:
                self._send_json(job.snapshot())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/start":
            try:
                data = self._body_json()
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
                    "event_filter": (set(data["events"]) if data.get("events") else None),
                    "detect_bidirectional": bool(data.get("detect_bidirectional", True)),
                }
                if params["r"] < 1 or not (0 <= params["t"] <= 100):
                    raise ValueError("r must be >= 1 and t in [0,100]")
            except (KeyError, ValueError, TypeError) as e:
                self._send_json({"error": f"bad input: {e}"}, 400)
                return
            job_id = MANAGER.start(params)
            self._send_json({"job": job_id})
        elif self.path == "/api/control":
            data = self._body_json()
            job = MANAGER.get(data.get("job", ""))
            if not job:
                self._send_json({"error": "unknown job"}, 404)
                return
            action = data.get("action")
            if action == "stop":
                job.request_stop()
            elif action == "continue":
                job.resume(True)
            elif action == "abort":
                job.resume(False)
            else:
                self._send_json({"error": "bad action"}, 400)
                return
            self._send_json({"ok": True})
        else:
            self.send_error(404)


def main():
    ap = argparse.ArgumentParser(description="Hasse Sequence Clustering web app")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Hasse Sequence Clustering running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
