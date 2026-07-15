"""
Fast generator for all labeled partial orders on {0, 1, ..., n-1}.

Strategy: backtracking + incremental transitive-closure propagation + bitmask rows.
Produces the same *set* of matrices as generate_posets.py (the brute-force
baseline) and the reference files posets_n4.json / posets_n5.json. Output is
unsorted (generation order); order carries no meaning.

Why it is fast:
  - We decide unordered pairs {i,j} (i<j) one at a time in a fixed order.
  - Each decision is one of: incomparable, i<j, or j<i.
  - After picking a relation we immediately force its transitive consequences
    (the entire closure), so most later pairs are already decided -> no branching.
  - A forced relation that contradicts an earlier decision (antisymmetry, or a
    pair we already committed as incomparable) prunes the whole subtree at once.

Bitmask representation (n small, so each row is one Python int):
  up[k]   = bitset of successors of k, including k   (bit j set  <=>  k <= j)
  down[k] = bitset of predecessors of k, including k (bit j set  <=>  j <= k)
  incomp[k] = bitset of elements explicitly committed incomparable to k

Usage:
  python generate_posets_fast.py          # generates n=5 (default)
  python generate_posets_fast.py 6        # generates n=6
"""

import json
import sys
import os


def generate_posets(n):
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    npairs = len(pairs)

    up = [1 << k for k in range(n)]       # up[k] starts as {k}
    down = [1 << k for k in range(n)]     # down[k] starts as {k}
    incomp = [0] * n

    results = []

    def add_le(a, b):
        """Force a <= b (a != b) and close transitively. Return False on conflict."""
        if up[a] >> b & 1:
            return True                   # already a <= b
        if up[b] >> a & 1:
            return False                  # b <= a exists -> antisymmetry violation
        if incomp[a] >> b & 1:
            return False                  # committed incomparable

        succs = up[b]                     # everything >= b (closed)
        preds = down[a]                   # everything <= a (closed)

        # New relations are exactly preds x succs. Check them before mutating.
        x = preds
        while x:
            xi = (x & -x).bit_length() - 1
            x &= x - 1
            y = succs
            while y:
                yj = (y & -y).bit_length() - 1
                y &= y - 1
                if xi == yj:
                    continue
                if up[yj] >> xi & 1:      # yj <= xi already -> cycle
                    return False
                if incomp[xi] >> yj & 1:  # committed incomparable -> conflict
                    return False

        # No conflict: apply the closed union.
        x = preds
        while x:
            xi = (x & -x).bit_length() - 1
            x &= x - 1
            up[xi] |= succs               # xi gains all successors of b
        y = succs
        while y:
            yj = (y & -y).bit_length() - 1
            y &= y - 1
            down[yj] |= preds             # yj gains all predecessors of a
        return True

    def set_incomp(i, j):
        """Commit {i,j} incomparable. Return False if already comparable."""
        if (up[i] >> j & 1) or (up[j] >> i & 1):
            return False
        incomp[i] |= 1 << j
        incomp[j] |= 1 << i
        return True

    def emit():
        results.append([[up[i] >> j & 1 for j in range(n)] for i in range(n)])

    def recurse(p):
        if p == npairs:
            emit()
            return
        i, j = pairs[p]

        # Already comparable from earlier propagation -> forced, no branching.
        if (up[i] >> j & 1) or (up[j] >> i & 1):
            recurse(p + 1)
            return
        # Already committed incomparable -> forced.
        if incomp[i] >> j & 1:
            recurse(p + 1)
            return

        # Undecided: branch on the three choices, snapshot/restore around each.
        snap_up = up[:]
        snap_down = down[:]
        snap_incomp = incomp[:]

        # 1) incomparable
        if set_incomp(i, j):
            recurse(p + 1)
        up[:] = snap_up
        down[:] = snap_down
        incomp[:] = snap_incomp

        # 2) i < j
        if add_le(i, j):
            recurse(p + 1)
        up[:] = snap_up
        down[:] = snap_down
        incomp[:] = snap_incomp

        # 3) j < i
        if add_le(j, i):
            recurse(p + 1)
        up[:] = snap_up
        down[:] = snap_down
        incomp[:] = snap_incomp

    recurse(0)

    return results


def main():
    import argparse
    import gzip

    parser = argparse.ArgumentParser(description="Generate all labeled posets on n elements.")
    parser.add_argument("n", nargs="?", type=int, default=5, help="number of elements (default 5)")
    parser.add_argument("--gzip", action="store_true",
                        help="write gzip-compressed .json.gz (recommended for n>=7)")
    parser.add_argument("--out", default=None,
                        help="output directory (default: this script's folder)")
    args = parser.parse_args()
    n = args.n

    print(f"Generating all labeled posets on {n} elements (backtracking + closure)...")
    posets = generate_posets(n)
    print(f"Found {len(posets)} posets.")

    out_dir = args.out or os.path.dirname(os.path.abspath(__file__))
    payload = json.dumps(posets, separators=(",", ":"))  # compact

    if args.gzip:
        out_path = os.path.join(out_dir, f"posets_n{n}.json.gz")
        with gzip.open(out_path, "wt", encoding="utf-8") as f:
            f.write(payload)
    else:
        out_path = os.path.join(out_dir, f"posets_n{n}.json")
        with open(out_path, "w") as f:
            f.write(payload)

    print(f"Saved to {out_path} ({os.path.getsize(out_path) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
