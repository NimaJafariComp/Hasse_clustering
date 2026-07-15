import ast
import pandas as pd
import itertools
import numpy as np
import os
import json

# Load sequences
script_dir = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(script_dir, 'plant_events_summary.csv'))
sequences = [ast.literal_eval(s) for s in df['sequence']]
names = list(df['name'])

# map name to class label
def map_label(name):
    n = name.lower()
    if 'axel' in n:
        return 'axel'
    if 'lutz' in n:
        return 'lutz'
    if 'salchow' in n:
        return 'salchow'
    if 'flip' in n:
        return 'flip'
    if 'toeloop' in n or 'toeloop' in name.lower() or 'toe_loop' in name.lower():
        return 'toe_loop'
    if 'loop' in n and 'toeloop' not in n:
        return 'loop'
    return 'unknown'

labels = [map_label(n) for n in names]
unique_events = sorted({e for seq in sequences for e in seq})

print('Unique events:', unique_events)

classes = sorted(set(labels))

# helper: build M_c for one sequence given extended_order
def build_M_c(seq, extended_order):
    m = len(extended_order)
    P = {e: set() for e in extended_order}
    for term_idx, term in enumerate(seq, 1):
        elements = list(term) if isinstance(term, tuple) else [term]
        for e in elements:
            if e in P:
                P[e].add(term_idx)
    M_c = [[0]*m for _ in range(m)]
    for i in range(m):
        for j in range(m):
            if i==j: continue
            P_i = P[extended_order[i]]
            P_j = P[extended_order[j]]
            if P_i and P_j and max(P_i) < min(P_j):
                M_c[i][j] = 1
    return np.array(M_c, dtype=int)

# evaluate a combination
def evaluate_comb(comb):
    extended_order = list(comb)
    # collect per-class matrices
    class_mats = {cl: [] for cl in classes}
    for seq, lab in zip(sequences, labels):
        M = build_M_c(seq, extended_order)
        class_mats[lab].append(M)
    # compute centroid per class (rounded mean)
    centroids = {}
    for cl in classes:
        mats = class_mats.get(cl, [])
        if len(mats)>0:
            centroid = np.round(np.mean(np.stack(mats), axis=0)).astype(int)
        else:
            centroid = None
        centroids[cl] = centroid
    # compute distinct centroids among classes that have centroids
    centroid_strings = {}
    for cl, c in centroids.items():
        if c is None:
            centroid_strings[cl] = None
        else:
            centroid_strings[cl] = c.tobytes()
    # count unique non-None centroids
    present = {cl: s for cl,s in centroid_strings.items() if s is not None}
    unique_vals = set(present.values())
    num_distinct = len(unique_vals)
    # find zero-distance pairs explicitly
    dists = {}
    cl_list = [cl for cl in classes if centroids[cl] is not None]
    zero_pairs = []
    for i in range(len(cl_list)):
        for j in range(i+1, len(cl_list)):
            v1 = centroids[cl_list[i]].flatten()
            v2 = centroids[cl_list[j]].flatten()
            dist = np.sum(np.abs(v1 - v2)) / len(v1)
            dists[(cl_list[i], cl_list[j])] = float(dist)
            if dist == 0.0:
                zero_pairs.append((cl_list[i], cl_list[j]))
    return {
        'comb': extended_order,
        'num_distinct': num_distinct,
        'zero_pairs': zero_pairs,
        'dists': dists
    }

# search all combinations
all_combs = list(itertools.combinations(unique_events, 5))
print(f'Testing {len(all_combs)} combinations...')

best = []
best_value = -1
for comb in all_combs:
    res = evaluate_comb(comb)
    nd = res['num_distinct']
    if nd > best_value:
        best_value = nd
        best = [res]
    elif nd == best_value:
        best.append(res)

print('\nBest number of distinct class centroids:', best_value)
print('Number of best combos found:', len(best))
# show top 10 best combos with their zero pairs
for i, r in enumerate(sorted(best, key=lambda x: x['comb'])[:20], 1):
    print(i, r['comb'], 'distinct:', r['num_distinct'], 'zero_pairs:', r['zero_pairs'])

# Also evaluate the user's suggested combo
user_comb = ('e1','e3','e5','e7','e9')
user_res = evaluate_comb(user_comb)
print('\nUser combo', user_comb, '-> distinct:', user_res['num_distinct'], 'zero_pairs:', user_res['zero_pairs'])

# save best list to JSON
out = {
    'best_value': best_value,
    'best_combinations': best,
    'user_combo': user_res
}
with open(os.path.join(script_dir, 'search_best_centroid_results.json'), 'w') as f:
    json.dump(out, f, indent=2)
print('\nSaved results to search_best_centroid_results.json')
