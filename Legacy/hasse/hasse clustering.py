from graphG_hasse import build_graph
import json
import numpy as np
import os
import networkx as nx
from collections import defaultdict
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
import dash
from dash import dcc, html, Output, Input, State
import plotly.graph_objs as go
import dash_bootstrap_components as dbc  # nicer default CSS
from matplotlib.colors import to_hex
from itertools import combinations
import time 

timings = {}

script_dir = os.path.dirname(__file__)
mc_json = os.path.join(script_dir, "M_c_matrices_diagonal_1 ('e1', 'e2', 'e5', 'e6', 'e11') corrupted10%.json")
with open(mc_json, "r") as f:
    M_c_data = json.load(f)
    
    
def plot_Gcp_coverage(G_cp, reach_sets, G, total_patients=125):

    coverage = {
        combo: len(set().union(*(reach_sets[n] for n in combo)))
        for combo in G_cp.nodes
    }

    combo_relation_counts = {
        combo: np.mean([np.sum(G.nodes[n]["matrix"]) for n in combo])
        for combo in G_cp.nodes
    }

    grouped_combos = defaultdict(list)
    for combo, avg_rel in combo_relation_counts.items():
        relation_level = int(round(avg_rel))  # integer level
        grouped_combos[relation_level].append(combo)

    pos = {}
    for y, level in enumerate(sorted(grouped_combos.keys(), reverse=True)):
        combos = grouped_combos[level]
        n = len(combos)
        x_coords = np.linspace(-5, 5, n) if n > 1 else [0]
        for x, combo in zip(x_coords, combos):
            pos[combo] = (x, level)

    values = list(coverage.values())
    norm = mcolors.LogNorm(vmin=1, vmax=max(values))
    cmap = plt.cm.YlOrRd
    node_colors = [cmap(norm(coverage[c])) for c in G_cp.nodes]

    fig, ax = plt.subplots(figsize=(18, 12))
    nx.draw_networkx_nodes(
        G_cp, pos, node_color=node_colors,
        node_size=400, ax=ax, alpha=0.9
    )
    nx.draw_networkx_edges(
        G_cp, pos, arrows=True, ax=ax,
        edge_color="gray", width=1, alpha=0.5
    )

    combo_labels = {
        combo: ",".join(map(str, combo)) for combo in G_cp.nodes
    }
    nx.draw_networkx_labels(
        G_cp, pos, labels=combo_labels, font_size=8, ax=ax
    )

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label="Coverage Count (log scale)")

    ax.set_title("G_cp Combo Graph – Hasse-style Reachability Layout", fontsize=14)
    ax.axis("off")
    plt.tight_layout()
    plt.show()



    
def find_best_combos(M, T_percent, reach_sets, G, total_patients=125):
    
    T = int(total_patients * T_percent / 100)
    all_nodes = [n for n in reach_sets if n != 0]  # skip node 0

    print(f"\nFinding combinations with size {M} with ≥{T_percent}% coverage ({T} patients)...")

    # Step 1: Find qualified combos
    qualified_combos = set()
    for size in range(1, M + 1):
        for combo in combinations(all_nodes, size):
            union_mc = set().union(*(reach_sets[n] for n in combo))
            if len(union_mc) >= T:
                qualified_combos.add(tuple(sorted(combo)))

    print(f"Found {len(qualified_combos)} high-coverage combinations.")
    
    # Step 2: Build directed graph G_cp
    G_cp = nx.DiGraph()
    for c in qualified_combos:
        G_cp.add_node(c)

    # Check descendant
    def all_nodes_covered_by_descendants(source_combo, target_combo):
        for g in source_combo:
            reachable = nx.descendants(G, g) | {g}
            if not any(h in reachable for h in target_combo):
                return False
        return True

    for a in qualified_combos:
        for b in qualified_combos:
            if a != b and all_nodes_covered_by_descendants(a, b):
                G_cp.add_edge(a, b)

    print(f"G_cp has {G_cp.number_of_nodes()} nodes and {G_cp.number_of_edges()} edges.")

    # Step 3: Find best combos = (no incoming edges)
    best_combos = [node for node in G_cp.nodes if G_cp.in_degree(node) == 0]
    print(f"Identified {len(best_combos)} best combinations (no incoming arrows).")

    return best_combos, G_cp


# remove diagonal from M_c
def remove_diagonal(matrix):
    return matrix * (1 - np.eye(matrix.shape[0], dtype=int))

M_c_matrices = [
    remove_diagonal(np.array(entry["M_c"], dtype=int))
    for entry in M_c_data
]


# Build Hasse graph G
from graphG_hasse import build_graph
t0 = time.time()
_, G = build_graph()  # You may use G_reduced if we want transitive reduction
hasse_matrices = [(G.nodes[i]["matrix"]) for i in G.nodes]
hasseI = (G.nodes[10]["matrix"])
timings["build_G_seconds"] = time.time() - t0
print(hasseI)

# Match M_c to a Hasse diagram node
t1 = time.time()
M_c_to_H_idx = []
for i, M_c in enumerate(M_c_matrices):
    match_idx = None
    for idx, H in enumerate(hasse_matrices):
        if np.array_equal(M_c, H):
            match_idx = idx
            break
    M_c_to_H_idx.append(match_idx)
    


    
    print(f"\nM_c #{i} matched to Hasse diagram node #{match_idx}")
    if match_idx is not None:
        print("Matched Hasse diagram matrix:")
        print(np.array_str(H))
    else:
        print("No match found.")


# Count reachability: n(d) = number of M_c that d can reach
reach_sets = defaultdict(set)
n_d = defaultdict(int)
for mc_idx, H_c in enumerate(M_c_to_H_idx):
    if H_c is None:
        continue
    reach_sets[H_c].add(mc_idx)
    n_d[H_c] += 1
    S_c = nx.descendants(G, H_c)
    for d in S_c:
        reach_sets[d].add(mc_idx)
        n_d[d] += 1
print("here are the reach sets for node 9 and 3")        
print(reach_sets[9])
print("----------------------------------------")  
print(reach_sets[3])

# Save reachability sets for all nodes
reach_sets_all_nodes = {
    str(node): sorted(list(mc_indices))
    for node, mc_indices in reach_sets.items()
}

reach_sets_file = os.path.join(script_dir, "reach_sets_all_nodes.json")
with open(reach_sets_file, "w") as f:
    json.dump(reach_sets_all_nodes, f, indent=2)

print(f"Reachability sets for all nodes saved to: {reach_sets_file}")



# Combine n(d) and len(reach_sets[d]) into one dictionary
combined_stats = {
    node: {"n(d)": n_d[node], "lnr": len(reach_sets[node]),"lnSC": len(nx.descendants(G, d))}
    for node in n_d
    for d in S_c
}

# Create DataFrame
df_result = pd.DataFrame.from_dict(combined_stats, orient="index")
df_result.index.name = "Hasse Diagram Index"
df_result = df_result.sort_index()


print(df_result)
# df_result.to_csv("n_d_counts.csv")

# # node color map based on n(d)
# node_values = [n_d.get(node, 1e-3) for node in G.nodes()]
# vmin = max(min(node_values), 1e-3)
# vmax = max(node_values)
# if vmax < vmin:
#     vmax = vmin + 1e-3
# lognorm = mcolors.LogNorm(vmin=vmin, vmax=vmax)
# cmap = plt.cm.YlOrRd
# node_colors = [cmap(lognorm(val)) for val in node_values]

# fig, ax = plt.subplots(figsize=(16, 12))
# ### reordering the nodes
# # count 1's in nodes
# node_relation_counts = {
#     node: int(np.sum(G.nodes[node]["matrix"]))
#     for node in G.nodes()
# }
# # Group nodes by relation
# grouped_nodes = defaultdict(list)
# for node, count in node_relation_counts.items():
#     grouped_nodes[count].append(node)
# #create position
# pos = {}
# for y, relation_level in enumerate(sorted(grouped_nodes.keys(), reverse=True)):
#     nodes = grouped_nodes[relation_level]
#     n = len(nodes)
#     x_coords = np.linspace(-5, 5, n) if n > 1 else [0]
#     for x, node in zip(x_coords, nodes):
#         pos[node] = (x, relation_level)  # x: horizontal spread, y: relation count

# nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=200, ax=ax)
# nx.draw_networkx_edges(G, pos, arrows=True, alpha=0.3, ax=ax)
# nx.draw_networkx_labels(G, pos, font_size=7, ax=ax)
# sm = plt.cm.ScalarMappable(cmap=cmap, norm=lognorm)
# sm.set_array([])
# cbar = plt.colorbar(sm, ax=ax, label="n(d) Reachability Count (log scale)")
# ax.set_title("Reachability Topography of Hasse Graph")
# ax.axis("off")
# plt.tight_layout()
# plt.show()

# #other style
# plt.figure(figsize=(12, 6))
# sns.heatmap(df_result.T, cmap="YlOrRd", annot=True, cbar=True)
# plt.title("Heatmap of Reachability Frequencies n(d)")
# plt.xlabel("Hasse Diagram Index")
# plt.ylabel("n(d)")
# plt.tight_layout()
# plt.show()

# #### interactive map--------------------#
# #---------------------------------------------------------------#
# # --- Dash App for Interactive n(d) Reachability Analysis ---
# app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# # Convert log-scaled n(d) values to color
# node_ids = list(G.nodes())
# node_x, node_y = [], []
# node_colors = []
# hover_texts = []

# min_val = min(node_values)
# max_val = max(node_values)

# # Amplify the layout to make spacing wider
# scale_x, scale_y = 15, 15 # increase if still crowded
# for node in pos:
#     x, y = pos[node]
#     pos[node] = (x * scale_x, y * scale_y)

# for node in node_ids:
#     x, y = pos[node]
#     node_x.append(x)
#     node_y.append(y)
#     nd_val = n_d.get(node, 1e-3)
#     node_colors.append(to_hex(cmap(lognorm(nd_val))))
#     hover_texts.append(f"Node {node}<br>n(d): {nd_val}<br>Relations: {node_relation_counts[node]}")
    

# # Edges
# edge_x, edge_y = [], []
# for src, dst in G.edges():
#     x0, y0 = pos[src]
#     x1, y1 = pos[dst]
#     edge_x += [x0, x1, None]
#     edge_y += [y0, y1, None]

# edge_trace = go.Scatter(
#     x=edge_x, y=edge_y,
#     mode='lines',
#     line=dict(color='gray', width=1),
#     hoverinfo='none'
# )

# node_trace = go.Scatter(
#     x=node_x, y=node_y,
#     mode='markers+text',
#     marker=dict(
#         size=20,
#         color=node_colors,
#         colorscale='YlOrRd',
#         cmin=0.0,
#         cmax=1.0,
#         colorbar=dict(title="n(d) (log scaled)"),
#         showscale=True,
#     ),
#     text=[str(n) for n in node_ids],
#     textposition='top center',
#     customdata=node_ids,
#     hovertext=hover_texts,
#     hoverinfo='text',
#     selected=dict(marker=dict(size=25, color='black')),
#     unselected=dict(marker=dict(opacity=0.6)),
# )

# # App layout
# app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# app.layout = dbc.Container([
#     html.H4("Interactive Reachability Viewer (n(d) Heatmap)"),
#     dcc.Graph(
#         id="hasse-graph",
#         style={'height': '1000px', 'width': '110%'},
#         figure=go.Figure(
#             data=[edge_trace, node_trace],
#             layout=go.Layout(
#                 title="Reachability Topography of Hasse Graph",
#                 clickmode='event+select',
#                 dragmode='lasso',
#                 showlegend=False,
#                 xaxis=dict(visible=False),
#                 yaxis=dict(visible=False),
#             )
#         ),
#         config={'scrollZoom': True, 'displayModeBar': True}
#     ),
#     html.Div(id='output-info', style={'marginTop': '1em', 'fontSize': '1.2em'}),
# ])

# @app.callback(
#     Output("output-info", "children"),
#     Input("hasse-graph", "selectedData")
# )
# def display_reachability(selectedData):
#     if not selectedData or "points" not in selectedData:
#         return "Select one or more nodes using lasso or box select."

#     selected_nodes = sorted(set(pt["customdata"] for pt in selectedData["points"] if pt["curveNumber"] == 1))
#     if not selected_nodes:
#         return "No nodes selected."

#     total_reachable_mc = set()
#     for node in selected_nodes:
#         total_reachable_mc.update(reach_sets.get(node, set()))

#     return f"Selected nodes: {selected_nodes} → Unique M_c reachables: {len(total_reachable_mc)} (~{len(total_reachable_mc)/125:.2%})"

#------------------------------------------------------------------------


# target_coverage = 0.85
# total_patients = 80
# min_required = int(total_patients * target_coverage)

# qualified_combinations = []

# # Exclude node 0
# all_nodes = [node for node in reach_sets.keys() if node != 0]

# # 1 to 5 node combinations
# for r in range(1, 5):  # r = 1 - 4
#     for combo in combinations(all_nodes, r):
#         combined_mc = set()
#         for node in combo:
#             combined_mc.update(reach_sets[node])
#         if len(combined_mc) >= min_required:
#             qualified_combinations.append({
#                 "nodes": combo,
#                 "coverage_count": len(combined_mc),
#                 "coverage_percent": f"{len(combined_mc)/total_patients:.2%}"
#             })

# # sort by fewest
# qualified_combinations.sort(key=lambda x: (len(x["nodes"]), -x["coverage_count"]))

# combo_output_file = os.path.join(script_dir, "high_coverage_node_combinations_up_to_5.json")
# with open(combo_output_file, "w") as f:
#     json.dump(qualified_combinations, f, indent=2)

# print("Top combinations (excluding node 0) covering ≥ 85% of patients:")
# for entry in qualified_combinations[:10]:
#     print(f"Nodes: {entry['nodes']} → Coverage: {entry['coverage_count']} ({entry['coverage_percent']})")

# print(f"\nSaved all qualified combinations to: {combo_output_file}")

#---------------------------------------------------------------------- for 6 edged nodes
# target_coverage = 0.85
# total_patients = 80
# min_required = int(total_patients * target_coverage)

# # Filter nodes whose matrix has exactly 6 edges (i.e., 6 ones)
# nodes_with_6_edges = [
#     node for node in reach_sets.keys()
#     if np.sum(G.nodes[node]["matrix"]) == 6 and node != 0
# ]

# print(f"Found {len(nodes_with_6_edges)} nodes with exactly 6 edges.")

# qualified_combinations = []

# # Try combinations of size 1 to 5
# for r in range(1, 6):
#     for combo in combinations(nodes_with_6_edges, r):
#         combined_mc = set()
#         for node in combo:
#             combined_mc.update(reach_sets[node])
#         if len(combined_mc) >= min_required:
#             qualified_combinations.append({
#                 "nodes": list(combo),
#                 "coverage_count": len(combined_mc),
#                 "coverage_percent": f"{len(combined_mc)/total_patients:.2%}"
#             })

# # Sort results
# qualified_combinations.sort(key=lambda x: (len(x["nodes"]), -x["coverage_count"]))

# # Save to file
# output_file = os.path.join(script_dir, "high_coverage_combos_nodes_with_6_edges.json")
# with open(output_file, "w") as f:
#     json.dump(qualified_combinations, f, indent=2)

# # Print top results
# print("\nTop combinations using nodes with 6 edges (≥ 85% coverage):")
# for entry in qualified_combinations[:10]:
#     print(f"Nodes: {entry['nodes']} → Coverage: {entry['coverage_count']} ({entry['coverage_percent']})")

# print(f"\nSaved {len(qualified_combinations)} qualifying combinations to: {output_file}")

#---------------------------------------------------------------

# # Assuming total number of items to cover is known (e.g., 10 symptoms or matrices or whatever domain elements)
# TOTAL_COVERAGE_SIZE = total_patients  # or whatever defines full coverage

# # Filter combos that give 100% coverage
# full_coverage_combos = [
#     entry for entry in qualified_combinations
#     if entry["coverage_count"] == TOTAL_COVERAGE_SIZE
# ]

# print(f"Found {len(full_coverage_combos)} combinations with 100% coverage.")

# # Save to JSON or CSV
# output_path = os.path.join(os.path.dirname(__file__), "full_coverage_combinations.json")
# with open(output_path, "w") as f:
#     json.dump(full_coverage_combos, f, indent=2)

# print(f"Saved full coverage combinations to {output_path}")

# # Remove generalizing combos: no arrows (edges) allowed between nodes in a combo
# def is_non_generalizing(combo, graph):
#     for i in range(len(combo)):
#         for j in range(i + 1, len(combo)):
#             u, v = combo[i], combo[j]
#             if graph.has_edge(u, v) or graph.has_edge(v, u):
#                 return False
#     return True

# non_generalizing_combos = [
#     entry for entry in full_coverage_combos
#     if is_non_generalizing(entry["nodes"], G)
# ]

# print(f"{len(non_generalizing_combos)} full-coverage combinations remain after removing generalizing pairs.")

# # Save to file
# output_path = os.path.join(script_dir, "non_generalizing_full_coverage_combos.json")
# with open(output_path, "w") as f:
#     json.dump(non_generalizing_combos, f, indent=2)

# print(f"Saved non-generalizing full coverage combos to {output_path}")


# --- Quick stats for 100 %-coverage combinations ---------------------------
# full_path = os.path.join(script_dir, "full_coverage_combinations.json")
# non_gen_path = os.path.join(script_dir, "non_generalizing_full_coverage_combos.json")

# with open(full_path, "r") as f:
#     full_coverage_combos = json.load(f)

# with open(non_gen_path, "r") as f:
#     non_generalizing_combos = json.load(f)

# total_full = len(full_coverage_combos)
# total_non_gen = len(non_generalizing_combos)
# print(f"\n=== Combination statistics ===")
# print(f"Full-coverage combos (100 %):       {total_full}")
# print(f"Non-generalizing combos (no edges): {total_non_gen}")
# if total_full:
#     print(f"Share that are non-generalizing:    {total_non_gen/total_full:.2%}")
# print("==================================\n")

# # Load the non-generalizing combinations
# input_path = os.path.join(script_dir,"non_generalizing_full_coverage_combos.json")
# with open(input_path, "r") as f:
#     combos = json.load(f)

# # Convert each combo to a frozenset for efficient comparison
# combo_sets = [frozenset(entry["nodes"]) for entry in combos]

# # Keep only sets that are not strict supersets of any other
# minimal_combos = []
# for i, s in enumerate(combo_sets):
#     if not any(s > other for j, other in enumerate(combo_sets) if i != j):
#         minimal_combos.append(combos[i])

# # Save result
# output_path = os.path.join(script_dir,"minimal_non_generalizing_full_coverage_combos.json")
# with open(output_path, "w") as f:
#     json.dump(minimal_combos, f, indent=2)

# print(f"Filtered down to {len(minimal_combos)} minimal combinations (no supersets).")
# print(f"Saved to: {output_path}")

# # Load full-coverage combinations
# with open(input_path, "r") as f:
#     full_combos = json.load(f)

# # Convert each combo to frozenset
# combo_sets = [frozenset(entry["nodes"]) for entry in full_combos]

# # Keep only combos that are not subsets or supersets of any others
# incomparable_combos = []
# for i, s in enumerate(combo_sets):
#     if all(not (s < other or s > other) for j, other in enumerate(combo_sets) if i != j):
#         incomparable_combos.append(full_combos[i])

# # Save the result
# output_path = os.path.join(script_dir,"incomparable_full_coverage_combos.json")
# with open(output_path, "w") as f:
#     json.dump(incomparable_combos, f, indent=2)

# print(f"Found {len(incomparable_combos)} mutually incomparable full-coverage combinations.")
# print(f"Saved to: {output_path}")

#-------------------------------------------------------------------------------------------
# Check if any node in a 100% combo has 9, 14, or 52 as descendants

# target_descendants = {9, 14, 52}

# combos_with_targets = []
# combos_without_targets = []


# for combo in full_coverage_combos:
#     has_target_descendant = False
#     nodes = set(combo["nodes"])
#     combo["includes_target_node"] = bool(nodes & target_descendants)


#     for node in nodes:
#         descendants = nx.descendants(G, node)
#         if target_descendants & descendants:
#             has_target_descendant = True
#             break  # no need to check further

#     combo["has_target_descendant"] = has_target_descendant
#     if has_target_descendant or combo["includes_target_node"]:
#         combos_with_targets.append(combo)
#     else:
#         combos_without_targets.append(combo)


# output_with = os.path.join(script_dir, "full_coverage_combos_with_target_descendants.json")
# output_without = os.path.join(script_dir, "full_coverage_combos_without_target_descendants.json")

# with open(output_with, "w") as f:
#     json.dump(combos_with_targets, f, indent=2)

# with open(output_without, "w") as f:
#     json.dump(combos_without_targets, f, indent=2)

# print(f"\nSaved combos WITH descendants (9/14/52) to: {output_with}")
# print(f"Saved combos WITHOUT descendants (9/14/52) to: {output_without}")
# print(f"Summary: {len(combos_with_targets)} with, {len(combos_without_targets)} without.")



#Greedy Approximate Algorithm for Set Cover Problem
#------------------------------------------------------#
total_patients = 125
target_coverage = 0.85
min_required = int(total_patients * target_coverage)

remaining_patients = set(range(total_patients))
covered_patients = set()
selected_nodes = []
nodes_to_consider = [node for node in reach_sets if node != 0]

while len(covered_patients) < min_required and nodes_to_consider:
    # node covering most patients
    best_node = max(
        nodes_to_consider,
        key=lambda n: len(reach_sets[n] - covered_patients)
    )
    new_covered = reach_sets[best_node] - covered_patients

    if not new_covered:
        break

    selected_nodes.append(best_node)
    covered_patients.update(new_covered)
    nodes_to_consider.remove(best_node)

# result
coverage_count = len(covered_patients)
coverage_percent = coverage_count / total_patients
print(f"\n Greedy Set Cover Result (excluding node 0):")
print(f"Selected Nodes: {selected_nodes}")
print(f"Patients Covered: {coverage_count} / {total_patients} ({coverage_percent:.2%})")

greedy_output = {
    "selected_nodes": selected_nodes,
    "coverage_count": coverage_count,
    "coverage_percent": f"{coverage_percent:.2%}"
}
output_path = os.path.join(script_dir, "greedy_set_cover_result.json")
with open(output_path, "w") as f:
    json.dump(greedy_output, f, indent=2)
print(f"Greedy cover saved to: {output_path}")


#-----------------------------------------------------#
#-----------------------------------------------------#


# Load the data
# with open(combo_output_file, "r") as f:
#     qualified_combinations = json.load(f)

# # Extract data for plotting
# labels = [",".join(map(str, entry["nodes"])) for entry in qualified_combinations]
# counts = [entry["coverage_count"] for entry in qualified_combinations]
# sizes = [len(entry["nodes"]) for entry in qualified_combinations]

# # Assign a color based on the number of nodes (combination size)
# unique_sizes = sorted(set(sizes))
# color_map = {size: plt.cm.tab10(i) for i, size in enumerate(unique_sizes)}
# colors = [color_map[size] for size in sizes]

# # Plot
# plt.figure(figsize=(12, 5))
# plt.bar(range(len(counts)), counts, color=colors)
# plt.xticks(range(len(counts)), labels, rotation=90, fontsize=8)
# plt.xlabel("Node Combinations")
# plt.ylabel("Coverage Count")
# plt.title("Qualified Combinations Sorted by Size and Coverage (≥85%)")
# # Add legend for size groups
# handles = [plt.Rectangle((0, 0), 1, 1, color=color_map[size]) for size in unique_sizes]
# plt.legend(handles, [f"{size} node(s)" for size in unique_sizes], title="Combo Size", loc="upper right")
# plt.tight_layout()
# plt.show()

#---------------------------------------------------
M = 2     
T = 90     

best_combos, G_cp = find_best_combos(M, T, reach_sets, G)

timings["hasse_clustering_seconds"] = time.time() - t1

for i, combo in enumerate(best_combos[:10]):  # Print top 10 for inspection
    print(f"Best Combo #{i+1}: {combo}")
    
import pandas as pd

df = pd.DataFrame(best_combos)
df.to_csv('best_combos.csv', index=False)

import json
script_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(script_dir,'best_combos.json'), 'w') as f:
    json.dump(best_combos, f, indent=2)

# Save timings in the same folder as the script
with open(os.path.join(script_dir, "timings_hasse_pipeline.json"), "w") as f:
    json.dump(timings, f, indent=2)


plot_Gcp_coverage(G_cp, reach_sets, G)



# if __name__ == "__main__":
#     app.run(debug=True)
