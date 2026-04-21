import PyWGCNA
import pandas as pd
import anndata as ad
import numpy as np
from classify_gene import classify_gene

df = pd.read_csv("data/expression_data/rna_tissue_consensus.tsv", sep='\t')
expr_df = df.rename(columns={'Gene_name': 'gene', 'Tissue': 'tissue', 'nTPM': 'median_tpm'})

protein_coding = expr_df['gene'].apply(lambda x: classify_gene(x)['type'] == 'HGNC Protein-Coding Gene Symbol')
expr_df = expr_df[protein_coding]

expr_matrix = expr_df.pivot_table(index='gene', columns='tissue', values='median_tpm')

threshold_tissues = 0.8 * expr_matrix.shape[1]
expr_matrix = expr_matrix.dropna(thresh=int(threshold_tissues))
expr_matrix = expr_matrix.fillna(0)
expr_matrix = np.log1p(expr_matrix)

adata = ad.AnnData(X=expr_matrix.T)

adata.obs = pd.DataFrame(index=expr_matrix.columns)
adata.obs['tissue_name'] = expr_matrix.columns

pywgcna = PyWGCNA.WGCNA(name="GTEx_Consensus", anndata=adata)

pywgcna.preprocess()

pywgcna.findModules()

pywgcna.moduleTraitCorrelation()

modules_df = pywgcna.modules

wgcna_module_dict = modules_df.groupby('module')['gene'].apply(list).to_dict()

with open("wgcna_modules.json", "w") as f:
    json.dump(wgcna_module_dict, f, indent=4)

print("WGCNA modules saved to wgcna_modules.json")