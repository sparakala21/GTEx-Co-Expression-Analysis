import networkx as nx
import matplotlib.pyplot as plt
import random
import igraph as ig
import pandas as pd
import json
def load_graph(file_path):
    G = nx.read_gexf(file_path)
    return G


def run_multiscale_clustering(G_nx):
    nodes = list(G_nx.nodes())
    mapping = {node: i for i, node in enumerate(nodes)}
    
    edges = [(mapping[u], mapping[v]) for u, v in G_nx.edges()]
    
    G_ig = ig.Graph(n=len(nodes), edges=edges, directed=False)
    
    weights = [G_nx[u][v].get('weight', 1.0) for u, v in G_nx.edges()]
    G_ig.es['weight'] = weights
    
    clusters = G_ig.community_multilevel(weights='weight', return_levels=True)

    final_partition = clusters[-1]
    
    module_dict = {}
    for i, cluster in enumerate(final_partition):
        module_dict[i] = [nodes[node_idx] for node_idx in cluster]
        
    return module_dict

if __name__ == "__main__":
    file_path = "data/GTEx_PMFG.gexf"
    G = load_graph(file_path)
    print(f"Graph loaded with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    module_dict = run_multiscale_clustering(G)
    print(f"Identified {len(module_dict)} modules.")
    output_filename = "megena_modules.json"
    with open(output_filename, 'w') as f:
        json.dump(module_dict, f, indent=4)
        
    print(f"Modules successfully saved to {output_filename}")