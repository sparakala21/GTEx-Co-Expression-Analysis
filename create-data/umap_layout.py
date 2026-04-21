import pandas as pd
from umap import UMAP

def create_layout_from_consensus(consensus_file):
    # 1. Load the data
    df = pd.read_csv(consensus_file, sep='\t')
    
    # 2. Pivot the table: Genes as rows, Tissues as columns
    # We keep both 'Gene' and 'Gene_name' in the index to preserve them during the pivot
    pivot_df = df.pivot(index=['Gene', 'Gene_name'], columns='Tissue', values='nTPM')
    
    # 3. Handle missing values
    pivot_df = pivot_df.fillna(0)
    
    print(f"Reshaped data: {pivot_df.shape[0]} genes x {pivot_df.shape[1]} tissues")
    
    # 4. Run UMAP
    reducer = UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
    layout = reducer.fit_transform(pivot_df.values)
    
    # 5. Create DataFrame
    layout_df = pd.DataFrame(
        layout, 
        columns=['x', 'y'], 
        index=pivot_df.index
    ).reset_index()

    # --- FORMATTING UPDATES ---
    # Rename 'Gene_name' to 'node'
    layout_df = layout_df.rename(columns={'Gene_name': 'node'})
    
    layout_df = layout_df[['node', 'x', 'y']]

    #normalize x and y to [0, 1]
    layout_df['x'] = (layout_df['x'] - layout_df['x'].min()) / (layout_df['x'].max() - layout_df['x'].min())
    layout_df['y'] = (layout_df['y'] - layout_df['y'].min()) / (layout_df['y'].max() - layout_df['y'].min())
    return layout_df

if __name__ == "__main__":
    consensus_path = "../data/expression_data/rna_tissue_consensus.tsv"
    
    # Changed extension to .csv
    output_path = "../data/expression_data/umap_layout.csv"
    
    result = create_layout_from_consensus(consensus_path)
    
    # Save as CSV (sep=',' is the default, but we'll be explicit)
    result.to_csv(output_path, sep=',', index=False)
    
    print(f"Layout saved to {output_path} in CSV format.")
    print(result.head())