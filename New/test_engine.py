"""
Tests for the Hasse Sequence Clustering core engine.

Includes a fully hand-worked example (sequences [a,b] and [a,b,c]) plus a
brute-force cross-check of the closed-relation enumerator.

Run:  python test_engine.py
"""

from itertools import combinations, chain

import engine
from engine import Dag


# --------------------------------------------------------------------------- #
# Brute-force reference for the closed-forward-relation enumerator
# --------------------------------------------------------------------------- #

def _brute_closed_relations(L):
    pairs = [(i, j) for i in range(L) for j in range(i + 1, L)]

    def is_closed(rel):
        s = set(rel)
        for (i, j) in s:
            for k in range(i + 1, j):
                if (i, k) in s and (k, j) in s and (i, j) not in s:
                    return False
        # also: any i<k<j with (i,k),(k,j) present forces (i,j)
        for (i, k) in s:
            for j2 in range(k + 1, L):
                if (k, j2) in s and (i, j2) not in s:
                    return False
        return True

    out = set()
    for size in range(len(pairs) + 1):
        for combo in combinations(pairs, size):
            if is_closed(combo):
                out.add(frozenset(combo))
    return out


def test_enumerator_matches_bruteforce():
    for L in range(1, 6):
        fast = set(engine.enumerate_closed_forward_relations(L))
        brute = _brute_closed_relations(L)
        assert fast == brute, f"closed-relation mismatch at L={L}"
    print("closed-relation enumerator matches brute force (L=1..5)")


# --------------------------------------------------------------------------- #
# Hand-worked example
# --------------------------------------------------------------------------- #

def D(*edges):
    """Build a Dag from cover edges (each a 2-tuple), computing the closure.

    Example: D(("a","b"), ("b","c"))  ->  a->b->c with closure including a->c.
    """
    cover = frozenset(edges)
    # closure: repeatedly compose
    closure = set(cover)
    changed = True
    while changed:
        changed = False
        for (a, b) in list(closure):
            for (c, d) in list(closure):
                if b == c and (a, d) not in closure:
                    closure.add((a, d))
                    changed = True
    return Dag(cover, frozenset(closure))


def test_step1_counts():
    s1 = engine.dags_for_sequence(["a", "b"])
    s2 = engine.dags_for_sequence(["a", "b", "c"])
    assert len(s1) == 1, f"S_1 expected 1, got {len(s1)}"
    assert len(s2) == 6, f"S_2 expected 6, got {len(s2)}"
    assert ("a", "b") in {e for dag in s1 for e in dag.edges}
    print("Step 1 counts OK (S_1=1, S_2=6)")


def test_step2_dedup():
    valid, n, _ = engine.preprocess([["a", "b"], ["a", "b", "c"]])
    assert n == 2
    S, si = engine.build_S_and_Si(valid)
    assert len(S) == 6, f"S expected 6 distinct, got {len(S)}"
    print("Step 2 dedup OK (|S|=6, n=2)")


def test_step3_r1_t100():
    valid, n, _ = engine.preprocess([["a", "b"], ["a", "b", "c"]])
    S, si = engine.build_S_and_Si(valid)
    C = engine.qualifying_subsets(S, si, r=1, t=100, n=n)
    # Only {a->b} reaches coverage 2 (covers both sequences).
    assert len(C) == 1, f"expected 1 singleton, got {len(C)}"
    only = next(iter(C[0]))
    assert only.edges == frozenset({("a", "b")}), only
    print("Step 3 (r=1, t=100) OK: only {a->b}")


def test_step3_antichain_excludes_comparable():
    valid, n, _ = engine.preprocess([["a", "b"], ["a", "b", "c"]])
    S, si = engine.build_S_and_Si(valid)
    C = engine.qualifying_subsets(S, si, r=2, t=100, n=n)
    # No qualifying subset may contain a comparable pair (one closure inside another).
    for subset in C:
        members = list(subset)
        for a, b in combinations(members, 2):
            assert engine._is_antichain_pair(a, b), f"comparable pair in C: {a}, {b}"
    # {a->b} alone still qualifies (coverage 2).
    assert any(s == frozenset({D(("a", "b"))}) for s in C)
    print("Step 3 antichain OK (no comparable pairs in any subset)")


def test_fast_source_scan_matches_full_scan_when_no_bidirectional_pair():
    sequences = [
        ["a", "b", "c"],
        ["a", "b", "d"],
        ["a", "c", "d"],
        ["a", "b", "c"],
        ["a", "b", "d"],
    ]
    valid, n, _ = engine.preprocess(sequences)
    S, si = engine.build_S_and_Si(valid)
    C = engine.qualifying_subsets(S, si, r=3, t=60, n=n)
    full_scan_sources = set(engine.find_sources(C, detect_bidirectional=True))
    fast_scan_sources = set(engine.find_sources(C, detect_bidirectional=False))
    assert fast_scan_sources == full_scan_sources, \
        "fast source detection must match full source detection when no halt occurs"
    print("Fast source detection matches full source detection")


def test_arrow_and_sources_smoke():
    # Two incomparable single-DAG vertices: neither arrows the other -> both sources.
    a = D(("a", "b"))
    b = D(("a", "c"))
    C = [frozenset({a}), frozenset({b})]
    sources = engine.find_sources(C)
    assert len(sources) == 2, sources
    # A vertex whose DAG closure contains another's: arrow exists, sparser is source.
    chain_dag = D(("a", "b"), ("b", "c"))   # a->b->c, closure has a->c
    single = D(("b", "c"))                   # closure {b->c} subset of chain closure
    C2 = [frozenset({chain_dag}), frozenset({single})]
    # arrow {chain} -> {single}? every Y in {chain} needs Z in {single} with
    # TC(Z) subset TC(Y): TC(single)={b->c} subset TC(chain)={a->b,b->c,a->c} -> yes.
    assert engine._arrow(frozenset({chain_dag}), frozenset({single}))
    assert not engine._arrow(frozenset({single}), frozenset({chain_dag}))
    print("Step 4-5 arrow/source smoke OK")


def test_repeat_semantics():
    # AlgV4 position-set rule: u may precede v iff max(P_u) < min(P_v).
    # In [a, x, b, x, c]: P_x = {1, 3}, so b (pos 2) sits between the x's ->
    # x and b are unrelated in every DAG; x->c and a->x remain allowed.
    si = engine.dags_for_sequence(["a", "x", "b", "x", "c"])
    closure_pairs = {p for dag in si for p in dag.closure}
    assert ("x", "b") not in closure_pairs and ("b", "x") not in closure_pairs, \
        "x and b must stay unrelated (b occurs between the two x's)"
    assert ("a", "x") in closure_pairs and ("x", "c") in closure_pairs
    # Every DAG's closure must respect the allowed partial order R.
    R = {("a", "x"), ("a", "b"), ("a", "c"), ("x", "c"), ("b", "c")}
    for dag in si:
        assert dag.closure <= R, f"DAG outside allowed order: {dag}"
    # All-repeats-overlapping row: R empty -> S_i empty (covers nothing).
    assert engine.dags_for_sequence(["a", "b", "a"]) == set()
    # Distinct-term rows are unchanged by the generalization.
    assert len(engine.dags_for_sequence(["a", "b", "c"])) == 6
    # preprocess keeps repeat rows now (counted, never dropped).
    valid, n, _ = engine.preprocess([["a", "b", "a"], ["a", "b"]])
    assert n == 2 and valid[0] == ["a", "b", "a"]
    # Rows emptied by the filter are out of scope: excluded from n; the kept
    # rows remember their original input positions.
    valid, n, idx = engine.preprocess([["q"], ["a", "b"], ["q", "a"]], {"a", "b"})
    assert n == 2 and valid == [["a", "b"], ["a"]] and idx == [1, 2]
    print("Step 1 repeat semantics OK (AlgV4 max(P_u) < min(P_v) rule)")


def test_analyze_rejects_noninteger_r():
    """The public API must preserve Step 3's integer subset-size bound."""
    for invalid_r in (1.5, True, "2"):
        try:
            engine.analyze([["a", "b"]], r=invalid_r, t=0)
        except ValueError as exc:
            assert str(exc) == "r must be a positive integer"
        else:
            raise AssertionError(f"analyze accepted non-integer r={invalid_r!r}")
    print("analyze rejects non-integer r")


if __name__ == "__main__":
    test_enumerator_matches_bruteforce()
    test_step1_counts()
    test_step2_dedup()
    test_step3_r1_t100()
    test_step3_antichain_excludes_comparable()
    test_fast_source_scan_matches_full_scan_when_no_bidirectional_pair()
    test_arrow_and_sources_smoke()
    test_repeat_semantics()
    test_analyze_rejects_noninteger_r()
    print("\nAll engine tests passed.")
