import networkx as nx
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import json
import os
from scipy.stats import hypergeom
from concurrent.futures import ThreadPoolExecutor, as_completed

def _test_clique(clique_id, member_ids, disease_dict, background_count):
    mod_genes_set = set(member_ids)
    N = len(mod_genes_set)
    if N == 0:
        return []
    
    local_results = []
    for mondo_id, disease_data in disease_dict.items():
        disease_genes = set(disease_data["genes"])
        overlap = mod_genes_set.intersection(disease_genes)
        x = len(overlap)
        if x == 0:
            continue
        p_val = float(hypergeom.sf(x - 1, background_count, len(disease_genes), N))
        if p_val < 0.05:
            local_results.append((clique_id, mondo_id, disease_data["diseaseName"], p_val, list(overlap)))
    return local_results

def init_db(cur, conn):
    cur.execute("""

        DROP TABLE IF EXISTS edges CASCADE;
        DROP TABLE IF EXISTS nodes CASCADE;
        DROP TABLE IF EXISTS cliques CASCADE;

        CREATE TABLE IF NOT EXISTS cliques (
            id           TEXT PRIMARY KEY,
            clique_type  TEXT CHECK (clique_type IN ('K3','K4')),
            level        INT,
            centroid_x   FLOAT,
            centroid_y   FLOAT,
            parent_id    TEXT REFERENCES cliques(id),
            member_ids   TEXT[],
            bbox         JSONB
        );
        CREATE TABLE IF NOT EXISTS nodes (
            id          TEXT PRIMARY KEY,
            x           FLOAT,
            y           FLOAT,
            label       TEXT,
            parent_id   TEXT REFERENCES cliques(id),
            expression  FLOAT[]
        );
        CREATE TABLE IF NOT EXISTS edges (
            id           BIGSERIAL PRIMARY KEY,
            source_id    TEXT,
            target_id    TEXT,
            level        INT,
            is_boundary  BOOL,
            weight       FLOAT,
            CONSTRAINT edges_unique UNIQUE (source_id, target_id, level, is_boundary)
        );
        CREATE TABLE IF NOT EXISTS disease_associations (
            module_id TEXT,
            mondo_id TEXT,
            disease_name TEXT,
            p_value FLOAT,
            overlap TEXT[]
        );
        CREATE INDEX IF NOT EXISTS idx_assoc_module ON disease_associations(module_id);
        CREATE INDEX IF NOT EXISTS idx_cliques_parent ON cliques(parent_id);
        CREATE INDEX IF NOT EXISTS idx_cliques_level  ON cliques(level);
        CREATE INDEX IF NOT EXISTS idx_edges_source   ON edges(source_id);
        CREATE INDEX IF NOT EXISTS idx_edges_level    ON edges(level);
    """)
    conn.commit()
    print("Database initialized")

def get_gene_expressions(genes, expression_data_path):
    """
    Pivots the dataframe to avoid nested loops, making it ~100x faster.
    """
    df = pd.read_csv(expression_data_path, sep='\t')
    
    # Standardize casing to avoid "Liver" vs "liver" mismatches
    df['Tissue'] = df['Tissue'].str.lower()
    
    # Pivot: Rows = Genes, Columns = Tissues
    # This creates a matrix where we can pull a whole row at once
    pivot_df = df.pivot_table(index='Gene_name', columns='Tissue', values='nTPM')
    
    # Ensure we include all tissues in a consistent order
    tissues = sorted(df['Tissue'].unique())
    pivot_df = pivot_df.reindex(columns=tissues)

    results = {}
    for gene in genes:
        if gene in pivot_df.index:
            # Convert row to list, replace NaN with None for Postgres compatibility
            results[gene] = [None if np.isnan(x) else float(x) for x in pivot_df.loc[gene].values]
        else:
            results[gene] = [None] * len(tissues)
    
    matches = sum(1 for v in results.values() if any(x is not None for x in v))
    print(f"Matched {matches} out of {len(genes)} genes across {len(tissues)} tissues")
    
    return results

def load_graph(graph_path):
    """Load network graph from GEXF file."""
    G = nx.read_gexf(graph_path)
    for u, v, data in G.edges(data=True):
        if 'weight' in data:
            data['weight'] = float(data['weight'])
    return G

def load_layout(layout_path):
    """Load 2D embeddings from CSV file."""
    embeddings = pd.read_csv(layout_path)
    names = embeddings['node'].tolist()
    emb_matrix = embeddings.drop(columns=['node']).to_numpy(dtype=float)
    print(f"Loaded layout with shape {emb_matrix.shape}")
    return names, emb_matrix

def build_layout_dict(G, names, emb_matrix):
    """Map node IDs that exist in G to (x, y) from the embedding matrix."""
    name_to_index = {name: idx for idx, name in enumerate(names)}
    layout = {}
    for node_id in G.nodes():
        if node_id in name_to_index:
            idx = name_to_index[node_id]
            layout[node_id] = (emb_matrix[idx, 0], emb_matrix[idx, 1])
        else:
            print(f"Warning: node {node_id} not found in layout, defaulting to (0, 0)")
            layout[node_id] = (0.0, 0.0)
    return layout

def export_nodes(G, layout, expressions, cur, conn):
    """
    Exports nodes ensuring float arrays are correctly formatted for Postgres.
    """
    rows = []
    for node_id, (x, y) in layout.items():
        label = G.nodes[node_id].get("label", str(node_id))
        expr_list = expressions.get(label)
        
        # Ensure we don't pass a raw 'None' to a FLOAT[] column
        # If no expression found, provide an empty array or array of NULLs
        if expr_list is None:
            expr_array = []
        else:
            expr_array = expr_list

        rows.append((str(node_id), float(x), float(y), label, expr_array, None))

    execute_values(cur, """
        INSERT INTO nodes (id, x, y, label, expression, parent_id)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET x=EXCLUDED.x, y=EXCLUDED.y, expression=EXCLUDED.expression
    """, rows)
    conn.commit()

def export_edges(G, level, cur, conn):
    """Export edges at a given hierarchical level."""
    rows = []
    for source, target, data in G.edges(data=True):
        rows.append((
            str(source),
            str(target),
            level,
            False,
            float(data.get("weight", 1.0))
        ))

    execute_values(cur, """
        INSERT INTO edges (source_id, target_id, level, is_boundary, weight)
        VALUES %s
    """, rows)
    conn.commit()
    print(f"Inserted {len(rows)} edges at level {level}")

def find_and_collapse_cliques(G, level, cur, conn, min_size=3, max_size=4):
    """
    Optimized to find specific small cliques and handle JSONB types correctly.
    """
    clique_rows = []
    edge_rows = []
    node_to_clique = {}
    
    all_cliques = []
    for c in nx.enumerate_all_cliques(G):
        if len(c) > max_size:
            continue
        if len(c) >= min_size:
            all_cliques.append(c)
        if len(all_cliques) > 5000:
            break

    used_nodes = set()
    selected_cliques = []
    for clique in sorted(all_cliques, key=len, reverse=True):
        if not any(n in used_nodes for n in clique):
            selected_cliques.append(clique)
            used_nodes.update(clique)

    G_new = G.copy()

    for i, members in enumerate(selected_cliques):
        clique_id = f"clique_{level}_{i}"
        member_ids = [str(m) for m in members]

        xs = [float(G.nodes[m].get("x", 0.0)) for m in members]
        ys = [float(G.nodes[m].get("y", 0.0)) for m in members]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)

        bbox = {"minX": min(xs), "maxX": max(xs), "minY": min(ys), "maxY": max(ys)}
        clique_type = f"K{len(members)}"

        clique_rows.append((
            clique_id, clique_type, level, cx, cy,
            None, member_ids, json.dumps(bbox)
        ))

        internal = set(members)
        # Collapse edges in the new graph
        G_new.add_node(clique_id, x=cx, y=cy)
        for m in members:
            for neighbor in list(G_new.neighbors(m)):
                if neighbor not in internal:
                    edge_rows.append((clique_id, str(neighbor), level + 1, True, 1.0))
                    G_new.add_edge(clique_id, neighbor)
        
        G_new.remove_nodes_from(members)
        for m in member_ids:
            node_to_clique[m] = clique_id

    # Batch Insert Cliques
    execute_values(cur, """
        INSERT INTO cliques (id, clique_type, level, centroid_x, centroid_y, parent_id, member_ids, bbox)
        VALUES %s ON CONFLICT (id) DO NOTHING
    """, clique_rows)

    # Batch Insert Boundary Edges
    if edge_rows:
        execute_values(cur, """
            INSERT INTO edges (source_id, target_id, level, is_boundary, weight)
            VALUES %s ON CONFLICT ON CONSTRAINT edges_unique DO NOTHING
        """, edge_rows)

    # Update parents in a single go
    if node_to_clique:
        node_pairs = list(node_to_clique.items())
        execute_values(cur, """
            UPDATE nodes SET parent_id = data.clique_id
            FROM (VALUES %s) AS data(node_id, clique_id)
            WHERE nodes.id = data.node_id
        """, node_pairs)

        execute_values(cur, """
            UPDATE cliques SET parent_id = data.clique_id
            FROM (VALUES %s) AS data(member_id, clique_id)
            WHERE cliques.id = data.member_id
        """, node_pairs)

    conn.commit()
    return G_new, G_new.number_of_nodes()

def perform_disease_enrichment(cur, conn, disease_dict, background_count):
    """
    Analyzes cliques stored in the database for disease enrichment.
    """
    # Fetch all cliques to treat as modules
    cur.execute("SELECT id, member_ids FROM cliques")
    cliques = cur.fetchall()
    
    results = []
    i=0
    cur.execute("SELECT id, member_ids FROM cliques")
    cliques = cur.fetchall()

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_test_clique, clique_id, member_ids, disease_dict, background_count): clique_id
            for clique_id, member_ids in cliques
        }
        for i, future in enumerate(as_completed(futures)):
            if i % 100 == 0:
                print(f"Processing clique {i}/{len(cliques)}")
            results.extend(future.result())
    cur.execute("""
        SELECT id FROM nodes
        WHERE id NOT IN (
            SELECT unnest(member_ids) FROM cliques
        )
    """)
    leaf_nodes = cur.fetchall()
    
    for (node_id,) in leaf_nodes:
        mod_genes_set = {node_id}
        for mondo_id, disease_data in disease_dict.items():
            disease_genes = set(disease_data["genes"])
            overlap = mod_genes_set.intersection(disease_genes)
            x = len(overlap)
            if x == 0: continue
            p_val = float(hypergeom.sf(x - 1, background_count, len(disease_genes), 1))
            if p_val < 0.05:
                results.append((node_id, mondo_id, disease_data["diseaseName"], p_val, list(overlap)))

    execute_values(cur, """
        INSERT INTO disease_associations (module_id, mondo_id, disease_name, p_value, overlap)
        VALUES %s
    """, results)
    conn.commit()
    print(f"Stored {len(results)} significant disease associations.")

def clear_database(cur, conn):
    """Clear all data from the database tables."""
    cur.execute("""
        TRUNCATE TABLE edges;
        TRUNCATE TABLE nodes CASCADE;
        TRUNCATE TABLE cliques CASCADE;
        TRUNCATE TABLE disease_associations CASCADE;
    """)
    conn.commit()
    print("Database cleared")


def run_pipeline(cur, conn, depth):
    """
    Main pipeline for processing multi-tissue network data.
    All file paths are defined here at the beginning.
    """
    # === FILE PATHS - CENTRALIZED HERE ===
    expression_data_path = "data/expression_data/rna_tissue_consensus.tsv"
    graph_path = "data/GTEx_PMFG.gexf"
    layout_path = "data/GTEx_PMFG_spring_layout.csv"
    disease_dict_path = "data/DisGeNET/disease_gene_relationships.json"

    
    print(f"Expression data: {expression_data_path}")
    print(f"Network graph: {graph_path}")
    print(f"Layout embeddings: {layout_path}")
    print()
    
    # Initialize database
    init_db(cur, conn)
    clear_database(cur, conn)
    
    # Load data
    print("Loading graph...")
    G = load_graph(graph_path)
    
    print("Loading layout...")
    names, emb_matrix = load_layout(layout_path)
    layout = build_layout_dict(G, names, emb_matrix)
    
    print("Loading gene expressions for all tissues...")
    expressions = get_gene_expressions(G.nodes(), expression_data_path)
    
    # Stamp x, y onto graph nodes so clique centroid math works
    for node_id, (x, y) in layout.items():
        G.nodes[node_id]["x"] = x
        G.nodes[node_id]["y"] = y

    # Export initial data
    print("Exporting nodes...")
    export_nodes(G, layout, expressions, cur, conn)
    
    print("Exporting edges...")
    export_edges(G, level=0, cur=cur, conn=conn)

    # Hierarchical clustering
    level = 0
    prev_count = G.number_of_nodes()

    for i in range(depth):
        print(f"\nProcessing level {level + 1}...")
        G, new_count = find_and_collapse_cliques(G, level=level, cur=cur, conn=conn)

        export_edges(G, level=level + 1, cur=cur, conn=conn)
        level += 1

        if new_count == prev_count:
            print(f"Converged at level {level} with {new_count} nodes")
            break
        prev_count = new_count

    print("Performing disease enrichment analysis...")
    with open(disease_dict_path) as f:
        disease_dict = json.load(f)
    background_count = len(set().union(*[set(d["genes"]) for d in disease_dict.values()]))
    perform_disease_enrichment(cur, conn, disease_dict, background_count)
    
    print("\nPipeline completed successfully!")


if __name__ == "__main__":
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    try:
        run_pipeline(cur, conn, depth=20)
    finally:
        cur.close()
        conn.close()

# if __name__ == "__main__":
#     DB_USER = "backend_user"
#     DB_PASS = "backend_password"
#     DB_HOST = "localhost"
#     DB_PORT = "5432"
#     DB_NAME = "backend_db"
    
#     connection_string = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
#     conn = psycopg2.connect(connection_string)
#     cur = conn.cursor()

#     try:
#         run_pipeline(cur, conn, depth=20)
#     finally:
#         cur.close()
#         conn.close()
        