"""
Generate all labeled partial orders on {0, 1, ..., n-1}.

Each poset is represented as an n×n binary matrix M where:
  M[i][j] = 1  iff  i <= j  in the partial order

Output: posets_n{n}.json — list of matrices in generation order (unsorted).
  Order carries no meaning; the *set* of matrices is what matters. As a set
  this matches posets_n4.json (219) and posets_n5.json (4231).

Usage:
  python generate_posets.py          # generates n=5 (default)
  python generate_posets.py 4        # generates n=4
  python generate_posets.py 6        # generates n=6 (slower)
"""

import json
import sys
import os
from itertools import product


def is_transitive(rel, n):
    for i in range(n):
        for j in range(n):
            if rel[i][j]:
                for k in range(n):
                    if rel[j][k] and not rel[i][k]:
                        return False
    return True


def generate_posets(n):
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]

    posets = []

    # For each unordered pair (i,j): 0=incomparable, 1=i<j, 2=j<i
    for assignment in product(range(3), repeat=len(pairs)):
        rel = [[0] * n for _ in range(n)]

        for idx, (i, j) in enumerate(pairs):
            if assignment[idx] == 1:
                rel[i][j] = 1
            elif assignment[idx] == 2:
                rel[j][i] = 1

        if not is_transitive(rel, n):
            continue

        mat = [row[:] for row in rel]
        for i in range(n):
            mat[i][i] = 1

        posets.append(mat)

    return posets


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    print(f"Generating all labeled posets on {n} elements...")
    print(f"Candidates to check: 3^{n*(n-1)//2} = {3**(n*(n-1)//2):,}")

    posets = generate_posets(n)
    print(f"Found {len(posets)} posets.")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"posets_n{n}.json")
    with open(out_path, "w") as f:
        json.dump(posets, f, indent=2)

    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
