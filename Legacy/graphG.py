import networkx as nx
import numpy as np
import json
import os
import pandas as pd

def build_graph():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file = os.path.join(script_dir, "posets_n5.json")

    with open(json_file, "r") as f:
        hasse_results = json.load(f)

    if isinstance(hasse_results, dict):
        all_matrices = []
        for m in sorted(hasse_results.keys(), key=int):
            all_matrices.extend(hasse_results[m])
    elif isinstance(hasse_results, list):
        all_matrices = hasse_results
    else:
        raise TypeError("posets_n5.json")


    num_matrices = len(all_matrices)
    print("Total matrices:", num_matrices)  #219

    # matrix to NumPy arr
    all_matrices_np = [np.array(mat) for mat in all_matrices]


    G = nx.DiGraph()
    ##G.add_nodes_from(range(num_matrices))   ## we have to attach matrices ot nodes
    for idx, mat in enumerate(all_matrices_np):
        G.add_node(idx, matrix=mat)


    # For each unordered pair (i, j), check if Matrix(j) - Matrix(i) has no negative entries.
    for i in range(num_matrices):
        for j in range(i + 1, num_matrices):
            
            diff_ij = all_matrices_np[j] - all_matrices_np[i]
            if np.all(diff_ij >= 0): #changed
                #G.add_edge(i, j)
                G.add_edge(j, i)
               
            
            diff_ji = all_matrices_np[i] - all_matrices_np[j]
            if np.all(diff_ji >= 0): #changed
                #G.add_edge(j, i)
                G.add_edge(i, j)
                

    print("Graph constructed with {} vertices and {} edges.".format(G.number_of_nodes(), G.number_of_edges()))
    adj_matrix = nx.to_numpy_array(G, dtype=int)
    df_adj = pd.DataFrame(adj_matrix, index=range(num_matrices), columns=range(num_matrices))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file_csv = os.path.join(script_dir, "final_graph_adjacency-posets_n5.csv")
    df_adj.to_csv(output_file_csv)

    print(f"Saved the adjacency matrix of final graph G to '{output_file_csv}'")

    # to make sure howm any rows and columns we have
    df_check = pd.read_csv(output_file_csv, index_col=0)
    num_rows, num_cols = df_check.shape
    print(f"\n")
    print(f"graph G has {num_rows} rows and {num_cols} columns.")



    # transitive reduction of the graph
    G_reduced = nx.transitive_reduction(G)
    # Preserve 'matrix' attributes from G to G_reduced
    for node in G_reduced.nodes():
        G_reduced.nodes[node]['matrix'] = G.nodes[node]['matrix']
    print("Transitive reduction has {} vertices and {} edges.".format(G_reduced.number_of_nodes(), G_reduced.number_of_edges()))

    adj_matrix_reduced = nx.to_numpy_array(G_reduced, dtype=int)
    df_adj_reduced = pd.DataFrame(adj_matrix_reduced, index=range(num_matrices), columns=range(num_matrices))

    output_file_reduced_csv = os.path.join(script_dir, "final_graph_adjacency-posets_n5_transitive_reduction.csv")
    df_adj_reduced.to_csv(output_file_reduced_csv)
    print(f"Saved the transitive reduction adjacency matrix to '{output_file_reduced_csv}'")

    mat_i = G.nodes[8]['matrix']
    mat_j = G.nodes[2]['matrix']
    print(mat_i)
    print(mat_j)



    # Compute all-pairs shortest path lengths
    ##
    #####
    G_undirected = G_reduced.to_undirected()
    # shortest_paths = nx.floyd_warshall_numpy(G_undirected)
    # df_shortest_paths = pd.DataFrame(shortest_paths, index=range(num_matrices), columns=range(num_matrices))


    # output_file_shortest_paths = os.path.join(script_dir, "shortest_path_distances-posets_n5.csv")
    # df_shortest_paths.to_csv(output_file_shortest_paths)
    # print(f"Saved shortest path distances between all pairs to '{output_file_shortest_paths}'")
    
    # Compute all-pairs shortest path lengths for directed G
    ##
    #####
    # shortest_paths = nx.floyd_warshall_numpy(G_reduced)
    # df_shortest_paths = pd.DataFrame(shortest_paths, index=range(num_matrices), columns=range(num_matrices))


    # output_file_shortest_paths = os.path.join(script_dir, "shortest_path_directed-posets_n5.csv")
    # df_shortest_paths.to_csv(output_file_shortest_paths)
    # print(f"Saved shortest path directed distances between all pairs to '{output_file_shortest_paths}'")

    ##reachability maatrix calc
    #####
    #####


    reachibility_matrix = np.zeros((num_matrices,num_matrices), dtype= int)

    for i in range(num_matrices):
        reachable = nx.descendants(G_undirected,i)
        for j in reachable:
            reachibility_matrix[i][j]=1
            
    np.fill_diagonal(reachibility_matrix,1)

    df_reachability = pd.DataFrame(reachibility_matrix, index=range(num_matrices), columns=range(num_matrices))
    output_file_reachability_matrix = os.path.join(script_dir, "reachability_matrix-posets_n5.csv")
    df_reachability.to_csv(output_file_reachability_matrix)
    print(f"Saved reachability matrix to '{output_file_reachability_matrix}'")
    
    return G, G_reduced

if __name__ == "__main__":
    G, G_reduced = build_graph()
