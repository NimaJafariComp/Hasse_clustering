# Hasse sequence clustering

`New/` is the current sequence-first Hasse clustering pipeline. It starts from raw event sequences, extracts compatible Hasse diagrams directly from the data, searches high-coverage antichain subsets, and reports source subsets plus row membership. It does not need the legacy precomputed poset universe, NetworkX graph, or fixed node IDs.

The broader framework is explainable process understanding. A sequence is not treated as a point in a feature vector space. It is treated as evidence for one or more partial-order process concepts: events, relations between events, abstraction/specialization structure, and difference-making constraints.

## Quick start

Run the browser UI:

```bash
cd New
python3 webapp/server.py
```

Open:

```text
http://127.0.0.1:8000
```

Run the command-line interface:

```bash
cd New
python3 run.py --sequences example_sequences.json -r 2 -t 60
python3 run.py --sequences example_sequences.json -r 3 -t 60 --events e1,e2,e3
```

Run tests:

```bash
cd New
python3 test_engine.py
```

## What this replaces

The legacy paper-parity path was:

```text
raw sequences
  -> AlgV4 strict per-sequence M_c matrices
  -> fixed precomputed Hasse universe
  -> graph over fixed node IDs
  -> high-coverage node combinations
  -> sources
```

The new path is:

```text
raw sequences
  -> sequence-compatible Hasse DAGs
  -> high-coverage antichain subsets
  -> source subsets under closure containment
  -> cluster membership by logical compatibility
```

This removes hard coupling to files such as `posets_n5.json`, `hasse_diagrams_n5.json`, `graphG.py`, and `graphG_hasse.py`. The new limit is still exponential in hard cases, but it is data-dependent rather than tied to a fixed precomputed universe.

## File map

```text
engine.py                  Core Hasse sequence algorithm
input_loader.py            JSON/CSV input parsing
run.py                     CLI entry point
test_engine.py             Engine tests and brute-force cross-checks
example_sequences.json     Small example input
SPEC.md                    Interpreted formal spec and history notes
webapp/server.py           Stdlib HTTP server and job manager
webapp/static/index.html   Browser UI markup
webapp/static/app.js       Browser API, rendering, heat map, refine panels
webapp/static/style.css    Browser UI styling
```

`engine.py` is the source of truth for current behavior. `SPEC.md` records the interpreted spec and older assumptions, so use this README plus the code for current behavior.

## Input model

Input is a list of event sequences. Each event is an arbitrary label.

JSON:

```json
[
  ["e1", "e2", "e5", "e6"],
  ["e2", "e5", "e11"],
  ["e2", "e1", "e5", "e6"]
]
```

CSV:

```csv
episode_id,sequence
ep_0,"['e2', 'e5', 'e1', 'e6', 'e9']"
ep_1,"['e2', 'e1', 'e5', 'e6', 'e9']"
```

CSV input uses a `sequence` column by default. Override with `--sequence-column` in the CLI or the matching field in the UI.

## Mathematical framework

Let the raw dataset be:

```text
X = (x_1, ..., x_N)
```

where each `x_i` is a finite sequence of event labels.

### Event filtering

Given an optional event set `E`, each sequence is restricted to:

```text
x_i|E = subsequence of x_i containing only labels in E
```

Rows that become empty after filtering are removed from the valid set. They are reported as `emptied by filter` and do not count toward `n`.

Rows with one remaining event stay in `n`, but they cannot be covered by any DAG because the engine excludes edgeless DAGs.

Therefore, if any valid row contains fewer than two related selected events, `t=100` may be unsatisfiable unless edgeless concepts are explicitly enabled in a future version.

### Position-set order relation

For a valid sequence `x_i`, define:

```text
P_i(a) = set of positions where event a occurs in x_i
```

The allowed precedence relation is:

```text
a <_i b  iff  max(P_i(a)) < min(P_i(b))
```

This is the AlgV4 position-set rule. Every occurrence of `a` must occur before every occurrence of `b`.

Important consequence:

```text
["a", "x", "b", "x", "c"]
```

allows `a < x`, `a < b`, `a < c`, `x < c`, and `b < c`, but it does not allow `x < b` or `b < x` because `b` occurs between the two `x` positions.

Repeats never drop a row. They only weaken the allowed relation.

### Per-sequence Hasse diagrams

For each valid sequence `x_i`, the engine constructs `S_i`, the set of all nonempty Hasse DAGs compatible with that row.

Mathematically:

```text
R_i = {(a, b) : a <_i b}
```

`R_i` is a strict partial order over the distinct event labels in `x_i`. The engine enumerates every nonempty transitively closed subrelation:

```text
Q subset R_i
```

Then it stores:

```text
H(Q) = transitive reduction of Q
```

`H(Q)` is the Hasse diagram. Its cover edges are used as the DAG identity. Its full transitive closure is also stored for containment checks.

The stored DAG uses only event labels that occur as endpoints of cover edges in `H(Q)`. Events that appear in the row but are unrelated to the selected relation are not stored as isolated vertices.

Thus:

```text
S_i = { H(Q) : Q is nonempty and transitively closed, Q subset R_i }
```

Edgeless DAGs are excluded. Isolated vertices are not stored because vertices are derived from edge endpoints.

### Global diagram set

The global set is:

```text
S = union_i S_i
```

Two DAGs are equal only if their labeled Hasse edge sets are equal. Event labels matter.

### Coverage

For any DAG `D in S`, define:

```text
cov(D) = { i : D in S_i }
```

For a subset `A subset S`:

```text
cov(A) = union_{D in A} cov(D)
```

Row `i` is covered by `A` when at least one DAG in `A` is compatible with row `i`.

### Qualifying subsets

Given:

```text
r = maximum subset size
t = coverage threshold percentage
n = number of valid rows
```

the engine builds `C`, the set of all nonempty subsets `A subset S` such that:

```text
1 <= |A| <= r
100 * |cov(A)| >= n * t
```

and `A` is an antichain under transitive-closure containment:

```text
not (TC(D_1) subset TC(D_2))
not (TC(D_2) subset TC(D_1))
```

for every distinct pair `D_1, D_2 in A`.

The antichain rule prevents one selected DAG from being only a constraint-weakening or constraint-strengthening of another selected DAG inside the same witness subset.

### Source-subset order

The paper-style order on qualifying subsets is:

```text
A -> B
```

iff:

```text
for every Y in A, exists Z in B such that TC(Z) subset TC(Y)
```

Interpretation:

```text
Z has fewer or equal constraints than Y
```

so `B` can generalize every DAG in `A`.

The engine returns source vertices of this directed graph: qualifying subsets with no incoming arrow. These are source subsets under the project rule, not centroids and not metric medoids.

Because arrows use the project's paper-style direction, `source` is a graph-theoretic output convention rather than a synonym for `most general` in ordinary language.

If bidirectional arrows are detected and bidirectional detection is enabled, the engine halts with a `ValueError`.

### Cluster membership

Each DAG inside each source subset is rendered as a cluster.

Row `i` belongs to DAG-cluster `D` iff:

```text
D in S_i
```

Equivalently:

```text
row i contains every event used by D
row i respects every transitive order constraint of D
```

This is logical compatibility, not distance minimization.

Rows may match several DAG-clusters. With `t < 100`, rows may match none.

## Algorithm in code

`engine.analyze()` runs the full pipeline:

```python
result = engine.analyze(
    sequences,
    r=2,
    t=100,
    event_filter={"e1", "e2", "e5", "e6", "e11"},
)
```

Returned keys:

```text
n                valid rows after filtering
n_loaded         raw input rows
n_empty          rows emptied by filter
S                distinct DAGs
C                qualifying subsets
sources          source subsets
valid_sequences  filtered rows kept in scope
valid_indices    original row indices for valid rows
source_members   per-source, per-DAG member row indices
```

Core functions:

```text
preprocess()                         event filtering and valid-row tracking
dags_for_sequence()                  Step 1 for one row
enumerate_closed_forward_relations() closed subrelation enumeration
build_S_and_Si()                     Steps 1-2 over all rows
qualifying_subsets()                 Step 3
find_sources()                       Steps 4-5
source_membership()                  cluster membership view
analyze()                            top-level driver
```

## Implementation notes

### Closed-relation enumeration

`enumerate_closed_forward_relations()` backtracks over allowed pairs and maintains closure using bitmasks:

```text
up[k]   = indices reachable from k
down[k] = indices that reach k
```

When it chooses `a < b`, it closes over all predecessors of `a` and successors of `b`. If closure would contradict a pair committed as unrelated, that branch is rejected.

This enumerates transitively closed subrelations without brute-forcing all subsets of all pairs.

### Hasse reduction

`_hasse_from_closure()` removes transitive edges. A pair `(i, j)` is a cover edge only when no intermediate `k` satisfies:

```text
(i, k) in Q and (k, j) in Q
```

The engine stores both:

```text
edges    Hasse cover edges, used for equality/hash/rendering
closure  full transitive closure, used for antichain/source tests
```

### Subset search

`qualifying_subsets()` uses:

```text
coverage sorted DAG order
Python int bitmasks for row coverage
closure bitmasks for antichain checks
suffix-union upper-bound pruning
periodic cancellation checks
```

It intentionally does not use dominated-DAG deletion or maximal-cover shortcuts because those changed `C` in earlier experiments.

### Source search

`find_sources()` avoids materializing all edges of the graph over `C`.

It builds integer closure-containment indexes, then checks whether each vertex has any incoming arrow. With `detect_bidirectional=False`, it can stop at the first incoming arrow for speed. With `detect_bidirectional=True`, it checks reverse arrows and halts on bidirectional pairs.

## CLI

Examples:

```bash
python3 run.py --sequences example_sequences.json -r 2 -t 60
python3 run.py --sequences example_sequences.json -r 3 -t 60 --events e1,e2,e3
python3 run.py \
  --sequences ../SampleV3GameData/sequence_of_sets_formatted_Won.csv \
  --format csv \
  --sequence-column sequence \
  -r 2 \
  -t 100 \
  --events e1,e2,e5,e6,e11
```

Flags:

```text
--sequences                 JSON or CSV input file
--format                    auto, json, or csv
--sequence-column           CSV sequence column, default sequence
-r                          maximum source-subset size
-t                          coverage threshold percentage, 0..100
--events                    comma-separated event filter
--no-bidirectional-check    faster source scan, skips bidirectional halt check
```

## Web UI

Start:

```bash
python3 webapp/server.py
python3 webapp/server.py --port 9000
```

The server uses only Python stdlib:

```text
ThreadingHTTPServer
background Job threads
engine.Control for progress, cancellation, and warnings
```

API:

```text
POST /api/start      start a job
GET  /api/status     poll a job
POST /api/control    stop, continue, or abort
```

UI features:

```text
JSON/CSV paste or upload
runtime warning modal
Stop button
summary metrics
source cards
SVG Hasse DAG rendering
cluster heat map
row-to-cluster assignment table
recursive refine panels
```

Refine panels run a full new `engine.analyze()` call on the rows covered by a selected cluster. Row labels keep original input positions so nested refinement remains traceable.

## Game v3 reference result

Run:

```bash
python3 run.py \
  --sequences ../SampleV3GameData/sequence_of_sets_formatted_Won.csv \
  --format csv \
  -r 2 \
  -t 100 \
  --events e1,e2,e5,e6,e11
```

Expected result:

```text
loaded rows              = 125
emptied by filter        = 0
valid sequences n        = 125
|S| (distinct DAGs)      = 126
|C| (qualifying subsets) = 137
sources                  = 1

Source subsets:
  1. { e1->e6 e2->e5 e5->e6  |  e2->e5 e5->e11 }
```

This matches the legacy paper pattern corresponding to old node IDs `(725, 343)`, but it is expressed directly as labeled Hasse edges.

Cluster view on this data:

```text
Cluster 1: e1->e6, e2->e5, e5->e6    74 rows
Cluster 2: e2->e5, e5->e11           51 rows
Overlap:                              0 rows
```

This is a hard partition because the dataset has two mutually exclusive winning endings and `t=100`. The algorithm does not guarantee hard partitions in general.

## Complexity and limits

This pipeline removes the fixed five-event wall from the legacy precomputed universe. It does not remove exponential worst-case behavior.

Main growth points:

```text
long rows with many distinct events
many diverse rows increasing |S|
larger r
lower t
large |C| during source detection
```

Runtime warnings appear when:

```text
sequence has at least 11 distinct events
|S| reaches at least 30
|C| reaches at least 3000
```

Practical guidance:

```text
Use event filters aggressively.
Start with r=1 or r=2.
Use high t first.
Inspect source DAGs, then refine clusters.
Expect exact search to become expensive on large diverse event vocabularies.
```

GPU acceleration is not expected to help much. The workload is branch-heavy graph/search logic, not dense numeric linear algebra.

## Current evaluation

Strengths:

```text
direct sequence input
labeled DAG identity
AlgV4-compatible repeat semantics
no precomputed poset universe
logical cluster membership
interactive refinement
clear process-concept interpretation
```

Tradeoffs:

```text
exact search can explode
source order is mathematically subtle
rows with one selected event count in n but cannot be covered
soft clustering can produce overlaps
SPEC.md contains some historical assumptions, so code is authoritative
```

Best interpretation:

```text
New/ extracts process concepts from event sequences.
Each Hasse DAG is a partial-order explanation: a set of event-order constraints
supported by one or more rows.
Each source subset is a high-coverage witness set selected by the project order.
Each cluster is logical row compatibility with one witness DAG, not distance to
a centroid.
Differences between DAGs expose difference-making constraints between process
patterns.
```
