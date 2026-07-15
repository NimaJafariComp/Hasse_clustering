"""
Tests for the poset generators.

Output is unsorted, so all comparisons are as SETS of matrices (order ignored).

Asserts:
  - Both generators produce the documented OEIS A001930 counts.
  - Each generator emits no duplicates (count == number of distinct matrices).
  - The fast generator yields the same set of matrices as the brute-force
    baseline for n=1..6.
  - Both match the reference files posets_n4.json and posets_n5.json as sets.
  - Artifact stability: applying the canonical sort to generator output
    reproduces the committed root reference files *exactly* (order included).
    This protects the file the clustering pipeline consumes — a silent reorder
    or regeneration that shifted node IDs would fail this test.

Run:  python test_generators.py
"""

import os
import json

import generate_posets as brute
import generate_posets_fast as fast

# OEIS A001930: number of labeled partial orders on n elements.
A001930 = {1: 1, 2: 3, 3: 19, 4: 219, 5: 4231, 6: 130023}

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def as_set(matrices):
    """Hashable set of matrices, order-independent."""
    return frozenset(tuple(tuple(row) for row in m) for m in matrices)


def canonical_sorted(matrices, n):
    """The historical canonical order of the root reference files:
    off-diagonal 1-count ascending, then row-major descending lexicographic.
    Encodes each matrix as one integer (descending lex == negated int).
    """
    def key(m):
        bits = 0
        off_diag_ones = 0
        for i in range(n):
            row = m[i]
            for j in range(n):
                v = row[j]
                bits = (bits << 1) | v
                if i != j:
                    off_diag_ones += v
        return (off_diag_ones, -bits)
    return sorted(matrices, key=key)


def test_counts_and_no_duplicates():
    for n, expected in A001930.items():
        b = brute.generate_posets(n)
        f = fast.generate_posets(n)
        assert len(b) == expected, f"brute n={n} count"
        assert len(f) == expected, f"fast n={n} count"
        # no duplicates: distinct-set size must equal list length
        assert len(as_set(b)) == expected, f"brute n={n} has duplicates"
        assert len(as_set(f)) == expected, f"fast n={n} has duplicates"
    print("counts OK + no duplicates (n=1..6, OEIS A001930)")


def test_fast_matches_brute_as_set():
    for n in range(1, 7):
        assert as_set(fast.generate_posets(n)) == as_set(brute.generate_posets(n)), \
            f"set mismatch n={n}"
    print("fast and brute produce the same set of matrices (n=1..6)")


def test_matches_reference_files_as_set():
    for n in (4, 5):
        ref_path = os.path.join(REPO_ROOT, f"posets_n{n}.json")
        if not os.path.exists(ref_path):
            print(f"reference posets_n{n}.json not found, skipping")
            continue
        with open(ref_path) as f:
            ref = as_set(json.load(f))
        assert as_set(brute.generate_posets(n)) == ref, f"brute vs reference n={n}"
        assert as_set(fast.generate_posets(n)) == ref, f"fast vs reference n={n}"
        print(f"both generators match reference posets_n{n}.json (as set)")


def test_canonical_order_reproduces_reference_files():
    """Artifact stability: sorted generator output == committed root file, exactly."""
    for n in (4, 5):
        ref_path = os.path.join(REPO_ROOT, f"posets_n{n}.json")
        if not os.path.exists(ref_path):
            print(f"reference posets_n{n}.json not found, skipping")
            continue
        with open(ref_path) as f:
            ref = json.load(f)
        assert canonical_sorted(fast.generate_posets(n), n) == ref, \
            f"canonical-sorted output != root posets_n{n}.json (order/content drift)"
        print(f"canonical sort reproduces root posets_n{n}.json exactly")


if __name__ == "__main__":
    test_counts_and_no_duplicates()
    test_fast_matches_brute_as_set()
    test_matches_reference_files_as_set()
    test_canonical_order_reproduces_reference_files()
    print("\nAll tests passed.")
