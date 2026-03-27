import pandas as pd
import numpy as np
import networkx as nx
import argparse
from sklearn.metrics.pairwise import cosine_similarity
from classify_gene import classify_gene

parser = argparse.ArgumentParser(description='Build gene co-expression similarity network')
parser.add_argument(
    '--metric',
    choices=['pearson', 'cosine'],
    required=True,
    help='Similarity metric to use: pearson or cosine'
)
parser.add_argument(
    '--threshold',
    type=float,
    default=0.7,
    help='Minimum similarity score to create an edge (default: 0.7)'
)
parser.add_argument(
    '--chunk-size',
    type=int,
    default=500,
    help='Number of genes per chunk (reduce if memory is still too high, default: 500)'
)
args = parser.parse_args()

# --- 1. Load and rename ---
df = pd.read_csv("expression_data/rna_tissue_consensus.tsv", sep='\t')
expr_df = df.rename(columns={'Gene_name': 'gene', 'Tissue': 'tissue', 'nTPM': 'median_tpm'})

# --- 2. Filter to protein-coding genes only ---
protein_coding = expr_df['gene'].apply(
    lambda x: classify_gene(x)['type'] == 'HGNC Protein-Coding Gene Symbol'
)
expr_df = expr_df[protein_coding]

# --- 3. Build gene x tissue matrix ---
expr_matrix = expr_df.pivot_table(index='gene', columns='tissue', values='median_tpm')
threshold_tissues = 0.8 * expr_matrix.shape[1]
expr_matrix = expr_matrix.dropna(thresh=int(threshold_tissues))
expr_matrix = expr_matrix.fillna(0)
expr_matrix = np.log1p(expr_matrix)

# --- 4. Fix: drop zero-variance genes (causes NaN in Pearson stddev divide) ---
gene_std = expr_matrix.std(axis=1)
zero_var = (gene_std == 0).sum()
if zero_var > 0:
    print(f"Dropping {zero_var} zero-variance genes (constant expression across all tissues)")
    expr_matrix = expr_matrix[gene_std > 0]

print(f"Expression matrix: {expr_matrix.shape[0]:,} genes x {expr_matrix.shape[1]} tissues")
print(f"Metric: {args.metric} | Threshold: {args.threshold} | Chunk size: {args.chunk_size}")

X = expr_matrix.values.astype(np.float32)   # float32 halves memory vs float64
genes = expr_matrix.index.to_numpy()
n = len(genes)

if args.metric == 'pearson':
    X_mean = X.mean(axis=1, keepdims=True)
    X_centred = X - X_mean
    X_norm = np.linalg.norm(X_centred, axis=1, keepdims=True)
    X_norm = np.where(X_norm == 0, 1, X_norm)
    X_ready = X_centred / X_norm                 
elif args.metric == 'cosine':
    X_norm = np.linalg.norm(X, axis=1, keepdims=True)
    X_norm = np.where(X_norm == 0, 1, X_norm)
    X_ready = X / X_norm

# --- 5. Chunked similarity — never build the full NxN matrix ---
# For each chunk of rows, dot against all rows with higher index (upper triangle)
edge_list = []
chunk_size = args.chunk_size

for start in range(0, n, chunk_size):
    end = min(start + chunk_size, n)
    chunk = X_ready[start:end]                        # (chunk_size, tissues)
    sim_block = chunk @ X_ready[start:].T             # (chunk_size, n - start)  ← upper triangle only

    # Find pairs above threshold (excluding diagonal / self-loops)
    rows_idx, cols_idx = np.where(sim_block >= args.threshold)
    cols_idx += start                                  # shift back to global index

    # Keep only strict upper triangle (col > row)
    mask = cols_idx > (rows_idx + start)
    rows_idx = rows_idx[mask] + start
    cols_idx = cols_idx[mask]

    if len(rows_idx):
        sims = sim_block[rows_idx - start, cols_idx - start]
        edge_list.append(pd.DataFrame({
            'gene_a': genes[rows_idx],
            'gene_b': genes[cols_idx],
            'profile_similarity': sims.astype(np.float32)
        }))

    if (start // chunk_size) % 5 == 0:
        print(f"  Processed genes {start}–{end} / {n} ...")

sim_edges = pd.concat(edge_list, ignore_index=True) if edge_list else pd.DataFrame(
    columns=['gene_a', 'gene_b', 'profile_similarity']
)
print(f"Total edges (threshold >= {args.threshold}): {len(sim_edges):,}")

# --- 6. Build graph and extract LCC ---
G = nx.from_pandas_edgelist(sim_edges, 'gene_a', 'gene_b', edge_attr=['profile_similarity'])
G_lcc = G.subgraph(max(nx.connected_components(G), key=len)).copy()
print(f"LCC: {G_lcc.number_of_nodes():,} nodes, {G_lcc.number_of_edges():,} edges")

# --- 7. Export ---
out_file = f"GTEx_combined_network_{args.metric}.gexf"
nx.write_gexf(G_lcc, out_file)
print(f"Exported to {out_file}")