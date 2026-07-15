"""
Hasse Sequence Clustering — core engine (Steps 1-6).

See SPEC.md for the interpreted specification and flagged assumptions.

A DAG is represented by the `Dag` class: a frozenset of Hasse (cover) edges plus
its transitive closure, both as frozensets of (label, label) tuples. Equality and
hashing are by the Hasse edge set, so identity is *labeled* (Step 2 dedup).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Iterator


# --------------------------------------------------------------------------- #
# Progress / cancellation control (used by the web UI; optional everywhere)
# --------------------------------------------------------------------------- #

class Cancelled(Exception):
    """Raised inside the engine when the caller requests a stop."""


class Control:
    """Optional hook object for progress reporting, stopping, and runtime
    warnings with a continue option. Passing ``None`` anywhere disables it.

    - progress_cb(stage: str, frac: float, message: str)
    - warn_cb(message: str) -> bool   # return True to continue, False to abort
    """

    def __init__(self, progress_cb=None, warn_cb=None):
        self.progress_cb = progress_cb
        self.warn_cb = warn_cb
        self._stop = False

    def request_stop(self):
        self._stop = True

    def check(self):
        if self._stop:
            raise Cancelled()

    def progress(self, stage, frac, message=""):
        if self.progress_cb:
            self.progress_cb(stage, max(0.0, min(1.0, frac)), message)

    def warn(self, message):
        """Surface a runtime warning. Aborts (raises Cancelled) if the caller's
        warn_cb returns False. With no warn_cb, warnings are ignored."""
        if self._stop:
            raise Cancelled()
        if self.warn_cb is not None and not self.warn_cb(message):
            raise Cancelled()


_NULL = Control()  # no-op default


# Heuristic thresholds at which the engine surfaces a runtime warning.
WARN_SEQUENCE_LEN = 11      # closed-relation enumeration grows fast past this
WARN_S_SIZE = 30            # subset search over S explodes combinatorially
WARN_C_SIZE = 3000          # source finding is O(|C|^2)


# --------------------------------------------------------------------------- #
# DAG representation
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Dag:
    edges: frozenset      # Hasse (cover) edges: frozenset[(u, v)]
    closure: frozenset    # transitive closure edges: frozenset[(u, v)]

    @property
    def vertices(self) -> frozenset:
        vs = set()
        for u, v in self.edges:
            vs.add(u)
            vs.add(v)
        return frozenset(vs)

    def __eq__(self, other) -> bool:
        return isinstance(other, Dag) and self.edges == other.edges

    def __hash__(self) -> int:
        return hash(self.edges)

    def __repr__(self) -> str:
        es = ", ".join(f"{u}->{v}" for u, v in sorted(self.edges))
        return f"Dag({es})"


def _hasse_from_closure(rel_pairs, labels) -> Dag:
    """Build a Dag from a transitively-closed relation over position pairs.

    rel_pairs: iterable of (i, j) position pairs with i < j (forward), closed.
    labels:    position -> event label.
    A pair (i, j) is a cover iff no k with (i, k) and (k, j) both in the relation.
    """
    rel = set(rel_pairs)
    cover = []
    for (i, j) in rel:
        redundant = any((i, k) in rel and (k, j) in rel for k in range(i + 1, j))
        if not redundant:
            cover.append((labels[i], labels[j]))
    closure = frozenset((labels[i], labels[j]) for (i, j) in rel)
    return Dag(frozenset(cover), closure)


# --------------------------------------------------------------------------- #
# Step 1 — enumerate S_i for one sequence
# --------------------------------------------------------------------------- #

def enumerate_closed_forward_relations(L: int, allowed_pairs=None) -> Iterator[frozenset]:
    """Yield every transitively-closed sub-relation of the allowed pairs on
    indices 0..L-1.

    allowed_pairs: list of (i, j) with i < j forming a TRANSITIVE relation
    (composition of two allowed pairs is allowed). Default None means all
    i < j — the total order, as for a distinct-event sequence. Transitivity
    guarantees closure forcing never creates a pair outside the allowed set.
    Closure is maintained incrementally via reachability bitmasks
    (up[k] = indices reachable from k, including k).
    Yields frozensets of (i, j) pairs, INCLUDING the empty relation.
    Backtracking with closure forcing — far cheaper than 2^|pairs| brute force.
    """
    if allowed_pairs is None:
        pairs = [(i, j) for i in range(L) for j in range(i + 1, L)]
    else:
        pairs = sorted(allowed_pairs)
    npairs = len(pairs)

    up = [1 << k for k in range(L)]     # up[k]: positions >= k reachable from k
    down = [1 << k for k in range(L)]   # down[k]: positions <= k that reach k
    notrel = [0] * L                    # notrel[i] bit j: pair {i,j} committed unrelated

    def add_le(a, b):
        """Force a < b (relate) and close. Return False on conflict."""
        if up[a] >> b & 1:
            return True                 # already related
        if notrel[a] >> b & 1:
            return False                # committed unrelated -> conflict
        preds = down[a]
        succs = up[b]
        # Check forced new pairs against unrelated commitments.
        x = preds
        while x:
            xi = (x & -x).bit_length() - 1
            x &= x - 1
            if notrel[xi] & succs:
                return False
        # Apply closure.
        x = preds
        while x:
            xi = (x & -x).bit_length() - 1
            x &= x - 1
            up[xi] |= succs
        y = succs
        while y:
            yj = (y & -y).bit_length() - 1
            y &= y - 1
            down[yj] |= preds
        return True

    def emit():
        rel = []
        for i in range(L):
            row = up[i]
            for j in range(i + 1, L):
                if row >> j & 1:
                    rel.append((i, j))
        return frozenset(rel)

    results = []

    def recurse(p):
        if p == npairs:
            results.append(emit())
            return
        i, j = pairs[p]
        if up[i] >> j & 1:              # already related by closure -> forced
            recurse(p + 1)
            return
        if notrel[i] >> j & 1:          # already unrelated -> forced
            recurse(p + 1)
            return

        snap_up, snap_down, snap_nr = up[:], down[:], notrel[:]

        # choice A: unrelated
        notrel[i] |= 1 << j
        notrel[j] |= 1 << i
        recurse(p + 1)
        up[:], down[:], notrel[:] = snap_up, snap_down, snap_nr

        # choice B: related (i < j)
        if add_le(i, j):
            recurse(p + 1)
        up[:], down[:], notrel[:] = snap_up, snap_down, snap_nr

    recurse(0)
    return iter(results)


def dags_for_sequence(seq: list) -> set:
    """Step 1: the set S_i of DAGs for one sequence, repeats allowed.

    Repeated events use AlgV4 position-set semantics: u may precede v in a DAG
    only when max(P_u) < min(P_v) — every occurrence of u before every
    occurrence of v. Those allowed pairs form a transitive partial order R
    (max(P_u) < min(P_v) and max(P_v) < min(P_w) imply max(P_u) < min(P_w)),
    and S_i = the Hasse DAGs of all nonempty closed sub-relations of R.
    For a distinct-term sequence R is the total position order, so this is
    exactly the original Step 1.
    """
    order = []                          # distinct events, first-occurrence order
    P = {}                              # event -> sorted occurrence positions
    for pos, e in enumerate(seq):
        if e not in P:
            P[e] = []
            order.append(e)
        P[e].append(pos)
    L = len(order)
    labels = {i: order[i] for i in range(L)}
    # max(P_i) < min(P_j) implies first-occurrence order, so i < j always.
    allowed = [(i, j) for i in range(L) for j in range(i + 1, L)
               if P[order[i]][-1] < P[order[j]][0]]
    out = set()
    for rel in enumerate_closed_forward_relations(L, allowed):
        if not rel:
            continue                    # exclude edgeless DAGs (Step 1.4)
        out.add(_hasse_from_closure(rel, labels))
    return out


# --------------------------------------------------------------------------- #
# Steps 1-2 — process all sequences
# --------------------------------------------------------------------------- #

def preprocess(sequences: list, event_filter=None):
    """Apply the optional event-filter, then drop rows that are empty after
    it (they contain no selected event, so they are out of scope for the
    filtered question and do NOT count toward n). Repeated events never drop
    a row: Step 1 handles them with AlgV4 position-set semantics
    (see dags_for_sequence).

    Returns (valid_sequences, n, valid_indices) where valid_indices maps each
    kept row back to its position in the input (for display).
    """
    valid = []
    indices = []
    for i, seq in enumerate(sequences):
        if event_filter is not None:
            seq = [e for e in seq if e in event_filter]
        if not seq:
            continue                    # emptied by filter -> out of scope
        valid.append(list(seq))
        indices.append(i)
    return valid, len(valid), indices


def build_S_and_Si(valid_sequences: list, control: Control = None):
    """Steps 1-2: per-sequence S_i list and the global deduplicated S."""
    ctl = control or _NULL
    total = len(valid_sequences) or 1
    si_list = []
    S = set()
    for idx, seq in enumerate(valid_sequences):
        ctl.check()
        if len(set(seq)) >= WARN_SEQUENCE_LEN:
            ctl.warn(
                f"Sequence #{idx + 1} has {len(set(seq))} distinct events; "
                f"enumerating its DAGs may take a long time. Continue?"
            )
        si = dags_for_sequence(seq)
        si_list.append(si)
        S |= si
        ctl.progress("enumerate", (idx + 1) / total,
                     f"Enumerated DAGs for sequence {idx + 1}/{total}")
    return list(S), si_list


# --------------------------------------------------------------------------- #
# Step 3 — qualifying subsets C
# --------------------------------------------------------------------------- #

def _coverage_index(S: list, si_list: list):
    """For each DAG in S, the set of sequence indices whose S_i contains it."""
    cov = {}
    for dag in S:
        cov[dag] = frozenset(i for i, si in enumerate(si_list) if dag in si)
    return cov


def _is_antichain_pair(a: Dag, b: Dag) -> bool:
    """True if neither closure contains the other (a, b are comparable-free)."""
    return not (a.closure <= b.closure or b.closure <= a.closure)


def qualifying_subsets(S: list, si_list: list, r: int, t: int, n: int,
                       control: Control = None):
    """Step 3: all antichain subsets of size 1..r meeting the coverage threshold.

    Same branch-and-bound shape as the original backtracker (coverage-descending
    order, suffix-union upper bound, incremental coverage), but the hot per-node
    operations run on Python ints instead of frozensets:
    - coverage union/count: int bitwise OR + bit_count (C speed, no allocation
      of set objects at every node);
    - antichain test: closure bitmasks, two AND/compare ops per chosen element
      instead of frozenset subset tests;
    - suffix bound: one OR + popcount against a precomputed suffix bitmask.
    No O(m^2) precomputation and no per-node candidate-list rebuilding — those
    were tried and cost more than they saved on large |S|.
    Returns a list of subsets, each a frozenset[Dag].
    """
    ctl = control or _NULL
    if len(S) >= WARN_S_SIZE:
        ctl.warn(
            f"|S| = {len(S)} distinct DAGs; the subset search (size <= {r}) can "
            f"grow very large. Continue?"
        )
    cov = _coverage_index(S, si_list)
    order = sorted(S, key=lambda d: len(cov[d]), reverse=True)
    m = len(order)

    # Coverage as Python int bitmasks: bit i set <-> sequence i covered.
    cov_bits = [sum(1 << i for i in cov[dag]) for dag in order]
    min_cov = -(-n * t // 100) if (n > 0 and t > 0) else 0  # ceil(n*t/100)

    # suffix_bits[k] = union (OR) of cov_bits[k:], for the upper bound.
    suffix_bits = [0] * (m + 1)
    for k in range(m - 1, -1, -1):
        suffix_bits[k] = suffix_bits[k + 1] | cov_bits[k]
    _pc = getattr(int, "bit_count", None) or (lambda x: bin(x).count("1"))

    # Closure bitmasks: each distinct closure edge gets a bit; a pair is an
    # antichain iff neither mask contains the other.
    edge_vocab: dict = {}
    for dag in order:
        for e in dag.closure:
            if e not in edge_vocab:
                edge_vocab[e] = len(edge_vocab)
    cl_bits = [sum(1 << edge_vocab[e] for e in dag.closure) for dag in order]

    results: list = []
    _step = [0]    # work counter for periodic stop-checks / progress
    _k0 = [0]      # current outer-loop index for mid-recurse progress messages
    chosen_ks: list = []   # index stack
    chosen_cl: list = []   # closure bitmasks of chosen, kept in sync

    def recurse(start: int, covered_bits: int, covered_cnt: int) -> None:
        # Record any non-empty chosen set that already meets the threshold.
        if covered_cnt >= min_cov:
            results.append(frozenset(order[k] for k in chosen_ks))
        if len(chosen_ks) == r:
            return
        for k in range(start, m):
            _step[0] += 1
            if _step[0] % 20000 == 0:
                ctl.check()
                ctl.progress("subsets", (_k0[0] + 1) / (m or 1),
                             f"Searching subsets from DAG {_k0[0] + 1}/{m} "
                             f"({len(results)} found, {_step[0]:,} steps)")
            # Upper bound: even adding all remaining coverage can't reach goal.
            if _pc(covered_bits | suffix_bits[k]) < min_cov:
                break  # order is by descending coverage; later are no better here
            ck = cl_bits[k]
            ok = True
            for cc in chosen_cl:
                # comparable (one closure contains the other) -> not an antichain
                if (ck & ~cc) == 0 or (cc & ~ck) == 0:
                    ok = False
                    break
            if not ok:
                continue
            new_bits = covered_bits | cov_bits[k]
            chosen_ks.append(k)
            chosen_cl.append(ck)
            recurse(k + 1, new_bits, _pc(new_bits))
            chosen_ks.pop()
            chosen_cl.pop()

    # Drive the top-level loop explicitly so we can report progress / check stop.
    # recurse() records the singleton {dag} at entry, then all valid extensions.
    for k0 in range(m):
        _k0[0] = k0
        ctl.check()
        ctl.progress("subsets", (k0 + 1) / (m or 1),
                     f"Searching subsets from DAG {k0 + 1}/{m} "
                     f"({len(results)} found, {_step[0]:,} steps)")
        if _pc(suffix_bits[k0]) < min_cov:
            break  # no subset starting at k0 or later can reach the threshold
        chosen_ks.append(k0)
        chosen_cl.append(cl_bits[k0])
        recurse(k0 + 1, cov_bits[k0], _pc(cov_bits[k0]))
        chosen_ks.pop()
        chosen_cl.pop()
    return results


# --------------------------------------------------------------------------- #
# Steps 4-5 — graph P and its sources
# --------------------------------------------------------------------------- #

def _arrow(A: frozenset, B: frozenset) -> bool:
    """Step 4 arrow rule: A -> B iff every Y in A has some Z in B with
    TC(Z) subset of TC(Y)."""
    for Y in A:
        if not any(Z.closure <= Y.closure for Z in B):
            return False
    return True


def find_sources(C: list, detect_bidirectional: bool = True,
                 control: Control = None):
    """Step 5: source vertices (in-degree 0) of P over vertex set C.

    Same arrow rule and results as the original frozenset scan, but the hot
    loop runs on precomputed integer bitmasks:
    - every distinct DAG's closure becomes an int over a shared edge vocab;
    - super_of[z] = bitmask of DAG indices whose closure contains z's;
    - contain_some[i] = union of super_of over vertex i's DAGs, so the arrow
      test B -> A collapses to "every DAG index of B has its bit set in
      contain_some[A]" — a couple of shifts per pair instead of frozenset
      subset tests.
    With detect_bidirectional=True every incoming arrow is reverse-checked
    and any A<->B pair raises ValueError (full pair coverage, as before);
    with False the scan stops at the first incoming arrow.
    """
    ctl = control or _NULL
    if len(C) >= WARN_C_SIZE:
        ctl.warn(
            f"|C| = {len(C)} vertices; finding sources is O(|C|^2). Continue?"
        )
    total = len(C) or 1

    # Distinct DAGs appearing in C, indexed.
    dag_index = {}
    for sub in C:
        for d in sub:
            if d not in dag_index:
                dag_index[d] = len(dag_index)
    dags = list(dag_index)
    m = len(dags)

    # Inverted index: edge_mask[e] = bitmask of DAG indices whose closure
    # contains edge e. Then super_of[z] (DAGs whose closure contains z's)
    # is the AND of edge_mask over z's closure edges — no m^2 pair loop.
    ctl.progress("sources", 0.0, f"Indexing closure containment ({m} DAGs)")
    edge_mask = {}
    for yi, d in enumerate(dags):
        bit = 1 << yi
        for e in d.closure:
            edge_mask[e] = edge_mask.get(e, 0) | bit
    super_of = [0] * m
    for zi, d in enumerate(dags):
        it = iter(d.closure)
        msk = edge_mask[next(it)]      # DAGs always have >= 1 edge
        for e in it:
            msk &= edge_mask[e]
        super_of[zi] = msk

    # contain_some[i]: DAG indices that contain some DAG of vertex i.
    vert_idx = [tuple(dag_index[d] for d in sub) for sub in C]
    contain_some = []
    for idxs in vert_idx:
        msk = 0
        for zi in idxs:
            msk |= super_of[zi]
        contain_some.append(msk)

    # Scan order: strong vertices first so the detect-off path exits early.
    n = len(C)
    strength = [max(len(dags[zi].closure) for zi in idxs) for idxs in vert_idx]
    order = sorted(range(n), key=lambda j: strength[j], reverse=True)

    sources = []
    for i in range(n):
        if i % 32 == 0:
            ctl.check()
            ctl.progress("sources", (i + 1) / total,
                         f"Checking vertex {i + 1}/{total} for incoming arrows")
        cs = contain_some[i]
        if detect_bidirectional:
            # Full scan: every incoming arrow gets a reverse check.
            incoming = [j for j in range(n)
                        if j != i and all((cs >> yi) & 1 for yi in vert_idx[j])]
            for j in incoming:
                csj = contain_some[j]
                if all((csj >> zi) & 1 for zi in vert_idx[i]):
                    raise ValueError(
                        "Bidirectional arrow detected between two vertices of P; "
                        "halting per spec (Step 4)."
                    )
            has_incoming = bool(incoming)
        else:
            # First incoming arrow disqualifies; strongest candidates first.
            has_incoming = any(
                j != i and all((cs >> yi) & 1 for yi in vert_idx[j])
                for j in order)
        if not has_incoming:
            sources.append(C[i])
    return sources


def canonical_subset_order(subset) -> list:
    """Deterministic DAG order within a subset (shared with serialization)."""
    return sorted(subset, key=lambda d: sorted(d.edges))


def source_membership(sources: list, si_list: list):
    """Cluster view of the sources: each DAG of a source subset is its own
    cluster, and sequence i belongs to that cluster iff the DAG is in S_i.
    A sequence may match several DAGs (within or across sources), or none.

    Returns a list parallel to `sources`; each entry is a list parallel to
    canonical_subset_order(subset), holding sorted lists of indices into the
    valid-sequence list.
    """
    return [
        [sorted(i for i, si in enumerate(si_list) if dag in si)
         for dag in canonical_subset_order(subset)]
        for subset in sources
    ]


# --------------------------------------------------------------------------- #
# Top-level driver
# --------------------------------------------------------------------------- #

def analyze(sequences: list, r: int, t: int, event_filter=None,
            detect_bidirectional: bool = True, control: Control = None):
    """Run Steps 1-5 and return a result dict.

    Keys: n (valid rows: non-empty after filtering), n_loaded (raw input
    rows), n_empty (rows emptied by the filter, excluded from n), S (list of
    Dag), C (list of frozenset[Dag]), sources (list of frozenset[Dag]),
    valid_sequences (the filtered rows), valid_indices (each valid row's
    position in the input), source_members (per-source, per-DAG covered
    valid-row indices, DAGs in canonical_subset_order).
    """
    if isinstance(r, bool) or not isinstance(r, int) or r < 1:
        raise ValueError("r must be a positive integer")
    if not (0 <= t <= 100):
        raise ValueError("t must be in [0, 100]")

    ctl = control or _NULL
    valid, n, valid_indices = preprocess(sequences, event_filter)
    S, si_list = build_S_and_Si(valid, control=ctl)
    C = qualifying_subsets(S, si_list, r, t, n, control=ctl)
    sources = find_sources(C, detect_bidirectional=detect_bidirectional, control=ctl)
    members = source_membership(sources, si_list)
    ctl.progress("done", 1.0, "Complete")
    return {"n": n, "n_loaded": len(sequences), "n_empty": len(sequences) - n,
            "S": S, "C": C, "sources": sources,
            "valid_sequences": valid, "valid_indices": valid_indices,
            "source_members": members}
