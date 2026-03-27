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
    G = nx.read_gexf("GTEx_PMFG.gexf")
    layout = create_layout(G)
    export_layout_to_csv(layout, "GTEx_PMFG_layout.csv")