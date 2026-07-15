"""
Hasse Sequence Clustering — command-line runner (core engine, Steps 1-6).

Reads sequences from a JSON or CSV file, runs the analysis, and prints the
source subsets with each DAG as a compact edge list.

Examples:
  python run.py --sequences example_sequences.json -r 2 -t 100
  python run.py --sequences example_sequences.json -r 3 -t 60 --events e1,e2,e5
"""

import argparse
import sys

import engine
from input_loader import parse_sequences_text


def render_dag(dag) -> str:
    """Compact left-to-right edge-list rendering."""
    if not dag.edges:
        return "(no edges)"
    return " ".join(f"{u}->{v}" for u, v in sorted(dag.edges))


def render_subset(subset) -> str:
    return "{ " + "  |  ".join(render_dag(d) for d in sorted(subset, key=lambda d: sorted(d.edges))) + " }"


def main():
    p = argparse.ArgumentParser(description="Hasse Sequence Clustering (Steps 1-6).")
    p.add_argument("--sequences", required=True,
                   help="JSON list of sequences, or CSV with a sequence column")
    p.add_argument("--format", choices=("auto", "json", "csv"), default="auto",
                   help="input format; default auto-detects from file contents")
    p.add_argument("--sequence-column", default="sequence",
                   help="CSV column containing Python/JSON-style sequence lists")
    p.add_argument("-r", type=int, required=True, help="max subset size (positive int)")
    p.add_argument("-t", type=int, required=True, help="coverage threshold percent (0-100)")
    p.add_argument("--events", default=None,
                   help="optional comma-separated event filter (preprocessing)")
    p.add_argument("--no-bidirectional-check", action="store_true",
                   help="skip bidirectional-arrow detection (faster source-only path)")
    args = p.parse_args()

    try:
        with open(args.sequences) as f:
            sequences = parse_sequences_text(
                f.read(),
                input_format=args.format,
                sequence_column=args.sequence_column,
            )

        event_filter = None
        if args.events:
            event_filter = set(e.strip() for e in args.events.split(",") if e.strip())

        result = engine.analyze(
            sequences, r=args.r, t=args.t, event_filter=event_filter,
            detect_bidirectional=not args.no_bidirectional_check,
        )
    except ValueError as e:
        print(f"HALT: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"loaded rows              = {result['n_loaded']}")
    print(f"emptied by filter        = {result['n_empty']} (out of scope, not in n)")
    print(f"valid sequences n        = {result['n']}")
    print(f"|S| (distinct DAGs)      = {len(result['S'])}")
    print(f"|C| (qualifying subsets) = {len(result['C'])}")
    print(f"sources                  = {len(result['sources'])}\n")

    print("Source subsets:")
    if not result["sources"]:
        print("  (none)")
    for i, subset in enumerate(result["sources"], 1):
        print(f"  {i}. {render_subset(subset)}")


if __name__ == "__main__":
    main()
