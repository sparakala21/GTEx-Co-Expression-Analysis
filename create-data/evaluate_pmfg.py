import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

def evaluate_pmfg(pmfg_path, original_path, weight_attr='profile_similarity'):
    print(f"--- Evaluating {pmfg_path} ---")
    G_pmfg = nx.read_gexf(pmfg_path)
    
    n = G_pmfg.number_of_nodes()
    e_pmfg = G_pmfg.number_of_edges()
    max_e = 3 * n - 6
    
    # 1. Validity Check
    is_planar, _ = nx.check_planarity(G_pmfg)
    
    # 2. Sparsity & Saturation
    saturation = (e_pmfg / max_e)
    
    # 3. Weight Preservation (Accuracy)
    pmfg_weights = [d.get(weight_attr, 0) for u, v, d in G_pmfg.edges(data=True)]
    
    avg_pmfg_w = np.mean(pmfg_weights)
    
    # 4. Topology (Meaningfulness)
    clustering = nx.average_clustering(G_pmfg)
    density = nx.density(G_pmfg)
    print(f"Number of nodes: {n}")
    print(f"Number of edges: {e_pmfg}")
    print(f"Max edges (Euler limit): {max_e}")
    # Output Results
    print(f"\n[VALIDITY]")
    print(f"  Planar:           {is_planar}")
    print(f"  Euler Limit:      {e_pmfg} <= {max_e} (Pass: {e_pmfg <= max_e})")
    
    print(f"  Avg Weight:       {avg_pmfg_w:.4f}")
    
    print(f"\n[MEANINGFULNESS]")
    print(f"  Saturation:       {saturation:.1%}")
    print(f"  Avg Clustering:   {clustering:.4f}")
    print(f"  Graph Density:    {density:.6f}")

    # Plot Degree Distribution
    degrees = [d for n, d in G_pmfg.degree()]
    plt.hist(degrees, bins=250, color='skyblue', edgecolor='black')
    plt.title("PMFG Degree Distribution")
    plt.xlabel("Degree")
    plt.ylabel("Frequency")
    plt.savefig("dd.png")

if __name__ == "__main__":
    # Update these paths to your actual filenames
    evaluate_pmfg("GTEx_PMFG.gexf", "GTEx_combined_network_pearson.gexf")