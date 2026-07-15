import json
import numpy as np
import os
import matplotlib.pyplot as plt

script_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(script_dir, "M_c_matrices_diagonal_1 ('e2', 'e3', 'e5', 'e8', 'e9').json")
with open(json_path, 'r') as f:
    data = json.load(f)

processed = []
for entry in data:
    M_c = entry['M_c']
    P_raw = entry['P']
    P = {k: set(v) if isinstance(v, list) else set([v]) if v is not None else set() for k, v in P_raw.items()}
    processed.append((M_c, P))

# import the method from newAlgV4 if available
from newAlgV4 import method2ForProcessed
M = method2ForProcessed(processed)
M = np.array(M)
labels = ['e2','e3','e5','e8','e9']

plt.figure(figsize=(6,5))
plt.imshow(M, cmap='Reds', vmin=0, vmax=1)
plt.colorbar(label='Consensus (0/1)')
plt.xticks(range(len(labels)), labels)
plt.yticks(range(len(labels)), labels)
for (i, j), val in np.ndenumerate(M):
    plt.text(j, i, int(val), ha='center', va='center', color='black')

plt.title('Consensus Matrix M (I_order = e2,e3,e5,e8,e9)')
out_path = os.path.join(script_dir, 'consensus_M_heatmap.png')
plt.tight_layout()
plt.savefig(out_path, dpi=150)
print(f"Saved heatmap to {out_path}")
