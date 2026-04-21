import networkx as nx
import pandas as pd

def create_layout(G):
    layout = nx.spring_layout(G)
    return layout
def export_layout_to_csv(layout, filename):
    df = pd.DataFrame(layout).T
    df.columns = ['x', 'y']
    df.to_csv(filename, index_label='node')

if __name__ == "__main__":
    G = nx.read_gexf("../data/GTEx_PMFG.gexf")
    print(f"Graph loaded with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    layout = create_layout(G)
    export_layout_to_csv(layout, "../data/GTEx_PMFG_spring_layout.csv")