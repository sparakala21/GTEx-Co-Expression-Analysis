import networkx as nx
import json
from itertools import combinations

def contract_graph_by_cliques(G, level, min_size=3, max_size=4):
    all_cliques = []
    for c in nx.enumerate_all_cliques(G):
        if min_size <= len(c) <= max_size:
            all_cliques.append(c)
        if len(all_cliques) > 10000: break

    used_nodes = set()
    selected_cliques = []
    for clique in sorted(all_cliques, key=len, reverse=True):
        if not any(n in used_nodes for n in clique):
            selected_cliques.append(clique)
            used_nodes.update(clique)

    G_new = G.copy()
    
    for i, members in enumerate(selected_cliques):
        clique_id = f"clique_{level}_{i}"
        
        flattened_members = []
        for m in members:
            if 'members' in G.nodes[m]:
                flattened_members.extend(G.nodes[m]['members'])
            else:
                flattened_members.append(m)
        
        G_new.add_node(clique_id, members=flattened_members)
        
        internal_set = set(members)
        for m in members:
            for neighbor in list(G_new.neighbors(m)):
                if neighbor not in internal_set:
                    G_new.add_edge(clique_id, neighbor)
        
        G_new.remove_nodes_from(members)
        
    return G_new

def iterative_clustering(G, iterations=3, k=3):
    current_G = G.copy()
    history = [current_G]
    
    for i in range(iterations):
        print(f"Iteration {i+1}: Graph has {current_G.number_of_nodes()} nodes, {current_G.number_of_edges()} edges.")
        
        contracted_G = contract_graph_by_cliques(current_G, k)
        
        if contracted_G.number_of_nodes() >= current_G.number_of_nodes():
            print(f"  Convergence reached at iteration {i+1}")
            break
        
        if contracted_G.number_of_nodes() < 1:
            print(f"  Graph contracted to nothing at iteration {i+1}")
            break
        
        current_G = contracted_G
        history.append(current_G)
    
    return history


def extract_modules(final_graph):

    module_dict = {}
    
    for node_id, data in final_graph.nodes(data=True):
        if 'members' in data:
            members = data['members']
            if isinstance(members, list):
                genes = []
                for item in members:
                    if isinstance(item, list):
                        genes.extend(item)
                    else:
                        genes.append(item)
            else:
                genes = [members]
            
            genes = list(dict.fromkeys(genes))
            module_dict[str(node_id)] = genes
    
    return module_dict


if __name__ == "__main__":
    print("Loading graph...")
    G = nx.read_gexf("data/GTEx_PMFG.gexf")
    print(f"Loaded graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    
    print("\nRunning iterative clustering...")
    layers = iterative_clustering(G, iterations=32, k=3)
    
    final_graph = layers[-1]
    print(f"\nFinal graph has {final_graph.number_of_nodes()} modules")
    
    module_dict = extract_modules(final_graph)
    
    with open("cpm_modules.json", 'w') as f:
        json.dump(module_dict, f, indent=4)
    
    print(f"Saved {len(module_dict)} modules to cpm_modules.json")
    
    total_genes = sum(len(genes) for genes in module_dict.values())
    print(f"Total genes in modules: {total_genes}")
    print(f"Average module size: {total_genes / len(module_dict):.1f}")