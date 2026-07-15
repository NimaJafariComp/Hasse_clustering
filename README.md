# Hasse Clustering

Research codebase for clustering event sequences by the **Hasse diagram (DAG)
patterns** they support, instead of by distances between feature vectors.

Broader framing: this project studies **explainable process understanding**.
Ologs can ground event labels as typed concepts and composable relations;
wiring diagrams represent process concepts as labeled event structures; Hasse
diagrams organize those structures by abstraction and specialization. In that
view, clustering is one use case. The larger goal is to extract, compare, and
explain process concepts from sequential data.

The core idea: every event sequence (e.g. one game episode) is compatible with
a set of partial orders over its events. The pipeline finds small **witness
sets of Hasse DAGs** that jointly cover a required fraction of the input
sequences, then keeps only the *source* witness sets under a
closure-containment ordering. Each DAG in a winning witness set acts as a
**cluster**: an input row belongs to it iff the row contains all of the DAG's
events in an order consistent with every edge (for repeated events, every
occurrence of the earlier event must precede every occurrence of the later —
the AlgV4 position rule). No distance metric, centroids, or feature
engineering.

## Repository Layout

```text
New/                 Current pipeline — start here
Legacy/              Old paper pipeline and earlier experiments
SampleV3GameData/    Game v3 sample dataset and result-comparison report
FigureSaktingData/   Figure-skating process-concept testbed and reports
```

### [New/](New/) — Hasse Sequence Clustering (current)

The sequence-first pipeline. Generates sequence-compatible Hasse DAGs directly
from the data (no precomputed poset universe), searches high-coverage antichain
subsets, finds source subsets, and reports per-DAG cluster membership of every
input row. Python stdlib only; runs on CPython or PyPy with no pip installs.

- [New/README.md](New/README.md) — full documentation: usage, the six-step
  algorithm, cluster-membership semantics, comparison with the old pipeline,
  performance notes.
- [New/SPEC.md](New/SPEC.md) — formal interpreted specification.
- [New/engine.py](New/engine.py) — core algorithm.
- [New/run.py](New/run.py) — CLI.
- [New/webapp/](New/webapp/) — dependency-free web UI with progress streaming,
  SVG DAG rendering, colored cluster boxes, and a row → cluster assignment
  table.

Quick start:

```bash
cd New
python3 webapp/server.py        # web UI at http://127.0.0.1:8000
python3 run.py --sequences example_sequences.json -r 2 -t 60   # CLI
python3 test_engine.py          # tests
```

### [Legacy/](Legacy/) — old paper pipeline

The original workflow, kept for paper parity and reference:

```text
raw sequences
  -> AlgV4 strict per-sequence ordering matrices (M_c)
  -> fixed precomputed poset/Hasse universe (posets_n5.json, ...)
  -> NetworkX graph over fixed node IDs
  -> high-coverage node combinations and sources
```

- [Legacy/AlgV4/](Legacy/AlgV4/) — `newAlgV4.py` builds per-sequence and
  consensus ordering matrices over a selected event set (see
  [NEW_ALG_V4_README.md](Legacy/AlgV4/NEW_ALG_V4_README.md)).
- [Legacy/poset_generator/](Legacy/poset_generator/) — generates all labeled
  posets on `n` elements (`posets_n1.json` … `posets_n7.json.gz`); counts
  follow OEIS A001930 (see its [README](Legacy/poset_generator/README.md)).
- [Legacy/hasse/](Legacy/hasse/) — old Hasse clustering over the fixed poset
  universe (`graphG_hasse.py`, `hasse_diagrams_n5.json`).
- [Legacy/graphG.py](Legacy/graphG.py), density-based and hierarchical
  clustering scripts — earlier experiments.

The legacy path is hard-coded to small fixed event universes (the `n=5` poset
files) and to positional node IDs such as `343` and `725`. The new pipeline
removes both constraints; its limits are data-dependent instead.

### [SampleV3GameData/](SampleV3GameData/) — Game v3 sample

Winning-episode sequences from the Game v3 experiment, used as the reference
dataset throughout:

- `sequence_of_sets_formatted_Won.csv` — 125 raw episode rows; input for the
  new pipeline (all 125 valid — repeated events are handled with AlgV4
  position-set semantics, never dropped).
- `M_c_matrices_diagonal_1 (…) game_won.json` — old AlgV4 output; input for the
  legacy pipeline.
- [GAME_V3_HASSE_SEQUENCE_RESULT_COMPARISON.md](SampleV3GameData/GAME_V3_HASSE_SEQUENCE_RESULT_COMPARISON.md)
  — side-by-side comparison of old and new results, plus the event dictionary
  (`e1` = key collected, `e2` = explosive collected, …).

On this data both pipelines agree on the best pattern. With `r=2, t=100` and
events `e1,e2,e5,e6,e11` the new pipeline finds one source of two DAGs:

```text
{ e1->e6 e2->e5 e5->e6  |  e2->e5 e5->e11 }
```

which clusters the 125 valid rows 74/51 with no overlap — a clean partition
here because the two DAGs describe mutually exclusive game endings (door route
vs. rock route). That partition is a property of this dataset; in general the
clustering is coverage-based and rows may match several DAGs or none. See
[New/README.md → Cluster Membership](New/README.md#cluster-membership-rows--witness-dags).

### [FigureSaktingData/](FigureSaktingData/) — figure-skating testbed

Figure-skating jump data used to test the framework as explainable process
understanding rather than flat classification. The event vocabulary encodes
direction, edge, toe-pick use, and landing relation. The key example is
Flip/Lutz: the jumps share most event structure but differ mainly by takeoff
edge, making them a compact test case for difference-making explanations.

- [FigureSaktingData/README.md](FigureSaktingData/README.md) — data notes and
  result summary.
- [FigureSaktingData/HUMAN_JUDGE_HASSE_HYPOTHESIS.tex](FigureSaktingData/HUMAN_JUDGE_HASSE_HYPOTHESIS.tex)
  — research note connecting figure-skating expertise, process concepts,
  Hasse wiring diagrams, cognition, and human-aligned AI.

## Which Pipeline Should I Use?

- Analyzing new sequence data → **New/** (direct, no precomputed universes, web
  UI, cluster membership).
- Reproducing the paper's exact counts and node IDs → **Legacy/** (AlgV4 +
  fixed poset universe).
