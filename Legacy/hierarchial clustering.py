import os
import numpy as np
import pandas as pd
import json
import networkx as nx
from collections import deque
from graphG import build_graph
import numpy as np
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import dendrogram
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import linkage, fcluster
from collections import defaultdict
from newAlgV4 import method2ForProcessed as M2
from pprint import pprint

script_dir = os.path.dirname(os.path.abspath(__file__))
directed_csv_path = os.path.join(script_dir, "shortest_path_directed-posets_n5.csv") #this should be changede too
df_directed = pd.read_csv(directed_csv_path, index_col=0)
directed_paths = df_directed.values

print("Precomputed directed shortest path matrix shape:", directed_paths.shape)

mc_json_path = os.path.join(script_dir, "M_c_matrices_diagonal_1 ('e1', 'e2', 'e5', 'e6', 'e11') corrupted10%.json")
with open(mc_json_path, "r") as f:
    mc_matrices = json.load(f)
mc_matrices_np = [np.array(entry["M_c"]) for entry in mc_matrices]
num_mc = len(mc_matrices_np)
print("Number of M_c matrices loaded:", num_mc)

# ----------------hierarchail with L1 norm------------------

vectors = np.array([mat.flatten() for mat in mc_matrices_np])
condensed_l1 = pdist(vectors, metric='cityblock')  # L1 distance vector
num_mc = len(vectors)
full_l1 = squareform(condensed_l1)

thresh = 3.0
labels = fcluster(Z, t=thresh, criterion='distance')

Z = linkage(condensed_l1, method='average')  # or 'single','complete',etc.


plt.figure(figsize=(10,5))
dendrogram(Z, labels=[str(i) for i in range(len(vectors))], leaf_rotation=90)
plt.title("Hierarchical Clustering with L1 Distance")
plt.xlabel("M_c index")
plt.ylabel("L1 distance")
plt.show()

# Print clusters
clusters_l1 = defaultdict(list)
for idx, lbl in enumerate(labels):
    clusters_l1[lbl].append(idx)

print(f"\nFinal clustering into {len(clusters_l1)} clusters (L₁ metric):\n")
for lbl, member_list in sorted(clusters_l1.items()):
    print(f"Cluster {lbl}: indices {member_list}")
    print()
    
for cluster_id in sorted(clusters_l1.keys()):
    indices = clusters_l1[cluster_id]
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
