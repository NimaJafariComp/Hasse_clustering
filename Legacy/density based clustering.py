import os
import json
import numpy as np
from sklearn.cluster import DBSCAN
from collections import defaultdict
from newAlgV4 import method2ForProcessed as M2


# a neighbor of a point p is any other point whose distance to p is ≤ ε (the radius eps).
# Density-based clustering groups points that have at least min_samples neighbors within a radius(“eps”), marking points with too few neighbors as noise

script_dir = os.path.dirname(__file__)
mc_json = os.path.join(script_dir, "M_c_matrices_diagonal_1 ('e1', 'e2', 'e5', 'e6', 'e11') corrupted10%.json")
with open(mc_json, "r") as f:
    mc_matrices = json.load(f)
    
X = np.array([np.array(entry["M_c"]).reshape(-1) for entry in mc_matrices])

# may need to experiment
eps = 2.0  # max L1-distance to be considered neighbors
min_samples = 1  # at least 2 points to form a dense region

db = DBSCAN(eps=eps, min_samples=min_samples, metric='manhattan')
labels = db.fit_predict(X)

print("DBSCAN cluster labels:")
for idx, lbl in enumerate(labels):
    print(f"  M_c index {idx:2d} → cluster {lbl}")

# display clus
clusters = defaultdict(list)
for idx, lbl in enumerate(labels):
    clusters[lbl].append(idx)

print("\nDensity-based clusters (–1 is noise):")
for lbl, members in clusters.items():
    print(f"  Cluster {lbl:2d}: M_c indices {members}")

#Cluster –1 (noise): Points that never had ≥ min_samples neighbors within eps, so they couldn’t join any dense region.

# convert loaded JSON P back into usable set form
for cluster_id, indices in clusters.items():
    print(f"\nProcessing Cluster {cluster_id} ({len(indices)} M_c entries):")

    # Prepare input for method2
    processed = [
        (
            mc_matrices[i]["M_c"],
            {k: set(v) for k, v in mc_matrices[i]["P"].items()}
        )
        for i in indices
    ]
    
    # Run method2 and display results
    M_result = M2(processed)
    print(f"Resulting matrix for cluster {cluster_id}:")
    for row in M_result:
        print(" ", row)