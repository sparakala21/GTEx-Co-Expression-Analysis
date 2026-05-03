import networkx as nx
import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import time
from functools import wraps
from collections import defaultdict


class Timer:
    def __init__(self, name="Operation"):
        self.name = name
        self.start = None
        self.elapsed = 0
    
    def __enter__(self):
        self.start = time.time()
        print(f"⏱️  [{self.name}] Starting...")
        return self
    
    def __exit__(self, *args):
        self.elapsed = time.time() - self.start
        print(f"✓ [{self.name}] Completed in {self.elapsed:.2f}s\n")

def time_function(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with Timer(func.__name__):
            return func(*args, **kwargs)
    return wrapper

def get_avg_k_core_degree(G):
    if G.number_of_nodes() == 0:
        return 0
    core = nx.k_core(G)
    if core.number_of_nodes() == 0:
        return 0
    return np.mean([d for _, d in core.degree()])

def get_metrics_fast(graph):
    degree_values = list(nx.degree_centrality(graph).values())
    print(f"Degree centrality computed: {len(degree_values)} values")
    triangles = sum(nx.triangles(graph).values()) // 3
    print(f"Triangles (3-cliques) counted: {triangles}")
    return {
        'Degree': np.mean(degree_values),
        'Cliques': triangles
    }

def load_graph(filepath):
    with Timer("Loading graph"):
        G = nx.read_gexf(filepath)
    return G

def generate_null_graphs(n, m, degree_dist):
    graphs = {}
    
    density = (2 * m) / (n * (n - 1)) if n > 1 else 0
    
    ba_m = max(1, int(m / n))  
    ws_k = max(2, int(2 * m / n))
    
    with Timer("Generating Erdos-Renyi graph"):
        graphs['ER'] = nx.erdos_renyi_graph(n=n, p=density)
    
    with Timer("Generating Chung-Lu graph"):
        graphs['CL'] = nx.expected_degree_graph(degree_dist, selfloops=False)
    return graphs

if __name__ == "__main__":
    overall_start = time.time()
    
    with Timer("Step 1: Loading original graph"):
        G = load_graph('data/GTEx_PMFG.gexf')
    
    with Timer("Step 2: Computing graph statistics"):
        degree_dist = [d for _, d in G.degree()]
        m = G.number_of_edges()
        n = G.number_of_nodes()
        print(f"Graph size: {n} nodes, {m} edges")
        print(f"Density: {nx.density(G):.4f}\n")
    
    with Timer("Step 3: Computing original graph metrics"):
        original_metrics = get_metrics_fast(G)
        print(f"Original metrics computed: {list(original_metrics.keys())}\n")
    
    data_list = []
    num_iterations = 3
    
    print("=" * 70)
    print(f"STARTING {num_iterations} ITERATIONS")
    print("=" * 70 + "\n")
    
    iteration_times = []
    
    for i in range(num_iterations):
        iter_start = time.time()
        print(f"\n{'='*70}")
        print(f"ITERATION {i + 1}/{num_iterations}")
        print('='*70)
        
        with Timer("  Generating null graphs"):
            null_graphs = generate_null_graphs(n, m, degree_dist)
        
        with Timer("  Computing metrics for all models"):
            results = {'Original': original_metrics}
            for name, graph in null_graphs.items():
                with Timer(f"    - {name} metrics"):
                    results[name] = get_metrics_fast(graph)
        
        with Timer("  Storing results"):
            for metric in ['Degree', 'Cliques']:
                data_list.append({
                    'Iteration': i + 1,
                    'Metric': metric,
                    'Original': results['Original'][metric],
                    'Erdos-Renyi': results['ER'][metric],
                    'Chung-Lu': results['CL'][metric],
                })
        
        iter_time = time.time() - iter_start
        iteration_times.append(iter_time)
        avg_iter_time = np.mean(iteration_times)
        remaining_iters = num_iterations - (i + 1)
        eta = avg_iter_time * remaining_iters
        
        print(f"Iteration time: {iter_time:.2f}s")
        print(f"Average iteration time: {avg_iter_time:.2f}s")
        if remaining_iters > 0:
            print(f"Estimated time remaining: {eta:.1f}s ({eta/60:.1f} minutes)\n")
    
    with Timer("Step 4: Preparing data for visualization"):
        df = pd.DataFrame(data_list)
        df_melted = df.melt(id_vars=['Iteration', 'Metric'], var_name='Model', value_name='Value')
        print(f"Data shape: {df_melted.shape}")
    
    with Timer("Step 5: Generating visualization"):
        g = sns.catplot(
            data=df_melted, kind="box",
            x="Model", y="Value", col="Metric",
            col_wrap=3, sharey=False,
            palette="muted", height=4, aspect=1.2
        )
        g.set_xticklabels(rotation=45)
        g.set(yscale="log")
        plt.tight_layout()
        plt.savefig('network_metrics_comparison.png', dpi=300, bbox_inches='tight')
        print("Saved: network_metrics_comparison.png")
    
    total_time = time.time() - overall_start
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"Total execution time: {total_time:.2f}s ({total_time/60:.2f} minutes)")
    print(f"Average time per iteration: {np.mean(iteration_times):.2f}s")
    print("=" * 70)