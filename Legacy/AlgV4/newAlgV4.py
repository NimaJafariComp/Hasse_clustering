import ast
import pandas as pd
import os
import numpy as np
import json

# def parse_sequence(seq_str):
#     I = {'e1', 'e2'}
#     try:
#         parsed = ast.literal_eval(seq_str)
#     except:
#         parsed = []
    
#     sequence = []
#     for term in parsed:
#         if isinstance(term, tuple):
#             filtered = [e for e in term if e in I]
#             if filtered:
#                 sequence.append(tuple(filtered))
#         elif term in I:
#             sequence.append(term)
#     return sequence

def method1(c_list, names=None):
    """Generate M_c and P^c based on the given sequence c_list.
    If `names` is provided (a parallel list of identifiers), print the name next to any M_c that is non-empty.
    """

    I_order = ['e3', 'e4', 'e5', 'e8']
    extended_order = I_order
    m = len(extended_order)  # changed to extended order
    processed = []
    n = 0
    
    for idx, c in enumerate(c_list):
        P = {e: set() for e in extended_order} #changed form i_order to extended order
        for term_idx, term in enumerate(c, 1):
            elements = list(term) if isinstance(term, tuple) else [term]
            for e in elements:
                if e in P:
                    P[e].add(term_idx)
        
        M_c = [[0]*m for _ in range(m)]
        
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                P_i = P[extended_order[i]] #changed
                P_j = P[extended_order[j]] #changed
                
                if P_i and P_j and max(P_i) < min(P_j):
                    M_c[i][j] = 1
                
        processed.append((M_c, P))
        M_c_array = np.array(M_c)
        if np.any(M_c_array):
            if names and idx < len(names):
                print(f"{names[idx]}:")
            print(M_c_array)
            n = n+1
            
    print(n)
    return processed


def method2ForProcessed(processed):
    # Use the same chosen order for Method 2 (Recommendation A)
    I_order = ['e3', 'e4', 'e5', 'e8']
    extended_order = I_order
    m = len(extended_order)  # changed from I_order
    M = [[0]*m for _ in range(m)]
    
    for i in range(m):
        for j in range(m):
            if i == j:
                continue
            ei = extended_order[i]
            ej = extended_order[j]
       
            condition_a = True
            for M_c_k, P_k in processed:
                if P_k[ei] and P_k[ej]:  # Only check if both are nonempty
                    if M_c_k[i][j] != 1:
                        condition_a = False
                        break  # No need to check further if one fails
                
        

            
            condition_b = any(
                P_k[ei] and P_k[ej] and max(P_k[ei]) < min(P_k[ej])
                for _, P_k in processed
            )
            
            if condition_a and condition_b:
                M[i][j] = 1
    
    return M

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_dir, "summary_node3_subset.csv")
    df = pd.read_csv(csv_file_path)
    
    c_list = [ast.literal_eval(symptom_set) for symptom_set in df["sequence"]]
    c_list2 = [
        ["e2", "e11", "e1", "e5", "e2"],  
        ["e9", "e6", "e1", "e6", "e9", "e2"],
        ["e2", "e2", "e11", "e1", "e5"], 
        ["e2", "e2","e2", "e2", "e11", "e1", "e5"], 
        ["e6", "e8", "e6", "e8", "e21", "e5", "e6", "e9"],


    ]
    names = list(df.get('name', []))
    processed = method1(c_list, names=names)
    M = method2ForProcessed(processed)
    
    #cluster0 = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122]
    #processed_subset = [processed[i] for i in cluster0]
    #M_consensus = method2ForProcessed(processed_subset)  # your existing Method 2

    
    print("Final Matrix M:")
    for row in M:
        print(row)
        

    
    names = list(df.get('name', []))
    selected_Mc_and_P = []
    for name, (M_c, P) in zip(names, processed):
        M_c_np = np.array(M_c)

        if np.any(M_c_np):  # selection criteria
            # Add 1s on the diagonal
            for i in range(len(M_c)):
                M_c[i][i] = 1

            # Convert P sets to sorted lists for JSON
            P_json = {k: sorted(list(P[k])) for k in P}

            selected_Mc_and_P.append({
                "name": name,
                "M_c": M_c,
                "P": P_json
            })

    print(f"Saving {len(selected_Mc_and_P)} matrices with P (names included)")

    out_path = os.path.join(script_dir, "M_c_matrices_diagonal_1 ('e3', 'e4', 'e5', 'e8').json")
    with open(out_path, "w") as f:
        json.dump(selected_Mc_and_P, f, indent=2)

    print(f"Saved to {out_path}")
    


# json_file_path = os.path.join(script_dir, "M_c_matrices_with_index.json")

# # 1. Load the file
# with open(json_file_path, "r", encoding="utf-8") as f:
#     cluster0_data = json.load(f)

# # 2. Build the processed list in the format Method 2 expects
# #    Each item is (M_c, P_dict_of_sets)
# processed = []
# for entry in cluster0_data:
#     M_c = entry["M_c"]
#     P_raw = entry["P"]
#     # Convert P’s lists back into sets
#     P = {k: set(v) if isinstance(v, list) else set([v]) if v is not None else set()
#          for k, v in P_raw.items()}
#     processed.append((M_c, P))

# # 3. Run Method 2
# M = method2ForProcessed(processed)

# # 4. Print result
# print("Consensus matrix from cluster0_inputs.json:")
# for row in M:
#     print(row)



# ######




