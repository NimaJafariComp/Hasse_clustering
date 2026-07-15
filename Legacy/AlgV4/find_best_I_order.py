import ast
import pandas as pd
import itertools

csv_file = 'plant_events_summary.csv'
df = pd.read_csv(csv_file)
sequences = [ast.literal_eval(s) for s in df['sequence']]

# collect unique event codes across sequences
unique = set()
for seq in sequences:
    for e in seq:
        unique.add(e)
unique = sorted(unique)
print('Unique events:', unique)

n = len(sequences)
best = []
best_count = -1

from collections import defaultdict

for comb in itertools.combinations(unique, 5):
    extended_order = list(comb)
    m = len(extended_order)
    count_nonempty = 0
    for seq in sequences:
        # build P mapping
        P = {e: set() for e in extended_order}
        for term_idx, term in enumerate(seq, 1):
            elements = list(term) if isinstance(term, tuple) else [term]
            for e in elements:
                if e in P:
                    P[e].add(term_idx)
        # compute M_c
        M_c = [[0]*m for _ in range(m)]
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                P_i = P[extended_order[i]]
                P_j = P[extended_order[j]]
                if P_i and P_j and max(P_i) < min(P_j):
                    M_c[i][j] = 1
        import numpy as np
        if np.any(np.array(M_c)):
            count_nonempty += 1
    if count_nonempty > best_count:
        best_count = count_nonempty
        best = [(extended_order, count_nonempty)]
    elif count_nonempty == best_count:
        best.append((extended_order, count_nonempty))

print(f'Best coverage: {best_count}/{n} videos')
# print top 10 best combos
for i, (comb, cnt) in enumerate(sorted(best, key=lambda x: -x[1])[:10], 1):
    print(i, comb, cnt)

# Also print top few combos by frequency using heuristic: try combos of most frequent events
freq = defaultdict(int)
for seq in sequences:
    for e in seq:
        freq[e] += 1

sorted_freq = sorted(freq.items(), key=lambda x: -x[1])
print('Event frequencies:', sorted_freq)

# show top 20 combos that achieve best_count (if many, limit output)
print('\nTop combos (limited):')
found = 0
for comb, cnt in best:
    print(comb, cnt)
    found += 1
    if found >= 20:
        break
