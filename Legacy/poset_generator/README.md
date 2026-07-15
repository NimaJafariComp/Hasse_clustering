# Poset Generator

Generate all **labeled** partial orders on `{0, 1, ..., n-1}`.

Each poset is an `n x n` binary matrix `M` where `M[i][j] = 1` iff `i <= j`.
Output is a JSON list of matrices in **generation order (unsorted)**. As a *set*
this matches the repo's `posets_n4.json` (219) and `posets_n5.json` (4231).

What order does and doesn't affect:
- **Set-based graph/clustering structure** (the partial-order DAG, reachability,
  clusters) is independent of order — reuse one fixed file and results are stable.
- **Numeric node IDs** are *not* order-independent. The analysis code derives
  node IDs from file position via `enumerate(...)`
  ([graphG.py](../graphG.py), [hasse/graphG_hasse.py](../hasse/graphG_hasse.py)),
  and some scripts name specific IDs like `G.nodes[343]`, `G.nodes[725]`,
  `G.nodes[10]`. Reorder the file and those numbers point at different matrices.

> Note: the original `posets_n*.json` files happened to be sorted. The
> generators no longer sort, because sorting was pure overhead (at `n=7` it was
> ~70% of runtime) and the math doesn't depend on order.
>
> This is safe for the clustering workflow: the poset file is **generated once
> and reused** — clustering reads that single fixed file every run, so within it
> index N always maps to the same matrix. Order only ever matters if you
> regenerate and swap the file mid-analysis (then old node indices like
> `G.nodes[343]` would point elsewhere). Don't do that; keep one committed file.

Counts follow [OEIS A001930](https://oeis.org/A001930):

| n | posets | stored in repo |
|---|--------|----------------|
| 1 | 1 | — (regenerate) |
| 2 | 3 | — |
| 3 | 19 | — |
| 4 | 219 | `posets_n4.json` (root, plain) |
| 5 | 4231 | `posets_n5.json` (root, plain) |
| 6 | 130023 | `posets_n6.json.gz` (root, ~0.35 MB) |
| 7 | 6129859 | `posets_n7.json.gz` (root, ~17 MB) |
| 8 | 431723379 | **not stored — infeasible** |

> **n=8 is not generated or stored.** 431M posets won't fit in RAM, and even
> gzipped the file would exceed 1 GB (past GitHub's 100 MB file limit). Counts
> beyond n=7 grow too fast to enumerate-and-store; the algorithm is correct for
> any n but practical storage stops at n=7.

Binary matrices compress ~40x, so n=6/n=7 are stored gzipped. Read any file
(plain or gzipped) with the helper:

```python
from poset_generator.load_posets import load_posets
mats = load_posets("posets_n7.json.gz")   # or "posets_n5.json"
```

## Two implementations

**`generate_posets.py` — brute-force baseline.**
Enumerates all `3^C(n,2)` pairwise assignments (incomparable / `i<j` / `j<i`)
and keeps the transitive ones. Simple and obviously correct; the reference for
all other code. Fine through `n=6` (~13s); impractical for `n>=7`.

**`generate_posets_fast.py` — backtracking + closure propagation + bitmask rows.**
Decides pairs one at a time, immediately forces every transitive consequence,
and prunes any branch that contradicts an earlier decision. Produces the
**same set of matrices** as the baseline.

### Measured speedup (this machine)

| n | brute | fast | speedup |
|---|-------|------|---------|
| 5 | 0.052s | 0.008s | ~6.1x |
| 6 | 13.0s  | 0.38s  | ~34.4x |
| 7 | impractical | 25s | — |

(Timings after dropping the final sort — see the note at the top.)

## Usage

```bash
python generate_posets.py 5                   # baseline, writes posets_n5.json
python generate_posets_fast.py 7 --gzip        # fast, writes posets_n7.json.gz
python generate_posets_fast.py 7 --gzip --out ..   # write to repo root
python test_generators.py                      # verify generators + references
```

Flags for `generate_posets_fast.py`: `--gzip` (compress output, recommended for
n>=7), `--out DIR` (output directory, default = the script's folder).
