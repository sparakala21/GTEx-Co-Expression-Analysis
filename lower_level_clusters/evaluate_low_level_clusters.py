import json
from scipy.stats import hypergeom
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib_venn import venn3

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def run_enrichment(disease_dict, module_dict, background_count):
    results = []
    for mod_name, mod_genes in module_dict.items():
        for mondo_id, disease_data in disease_dict.items():
            disease_genes = set(disease_data["genes"])
            mod_genes_set = set(mod_genes)
            
            overlap = mod_genes_set.intersection(disease_genes)
            x = len(overlap)
            
            M = background_count
            n = len(disease_genes)
            N = len(mod_genes_set)
            
            if N > 0:
                p_val = hypergeom.sf(x - 1, M, n, N)
                if p_val < 0.05:  
                    results.append({
                        "Module": mod_name,
                        "MONDO_ID": mondo_id,
                        "DiseaseName": disease_data["diseaseName"],
                        "P_value": p_val,
                        "Overlap": list(overlap)
                    })
    return results

def process_results(results, method_name):
    df = pd.DataFrame(results)
    if not df.empty:
        df['Method'] = method_name
        df['neg_log_p'] = -np.log10(df['P_value'])
    else:
        df = pd.DataFrame(columns=['Module', 'MONDO_ID', 'DiseaseName', 'P_value', 'Overlap', 'Method', 'neg_log_p'])
    return df


disease_dict = load_json('../data/DisGeNET/disease_gene_relationships.json')
wgcna_modules = load_json('wgcna_modules.json')
megena_modules = load_json('megena_modules.json')
cpm_modules = load_json('cpm_modules.json')
#Clique Percolation Method

all_genes = set()
for mod in wgcna_modules.values(): all_genes.update(mod)
bg_count = len(all_genes)
print(f"Background gene count for enrichment: {bg_count}")
wgcna_results = run_enrichment(disease_dict, wgcna_modules, bg_count)
print(f"WGCNA enrichment completed with {len(wgcna_results)} significant results.")
megena_results = run_enrichment(disease_dict, megena_modules, bg_count)
print(f"MEGENA enrichment completed with {len(megena_results)} significant results.")
cpm_results = run_enrichment(disease_dict, cpm_modules, bg_count)
print(f"CPM enrichment completed with {len(cpm_results)} significant results.")

eval_data = {"WGCNA": wgcna_results, "MEGENA": megena_results, "CPM": cpm_results}


wgcna_df = process_results(eval_data['WGCNA'], 'WGCNA')
megena_df = process_results(eval_data['MEGENA'], 'MEGENA')
cpm_df = process_results(eval_data['CPM'], 'CPM')

full_df = pd.concat([wgcna_df, megena_df, cpm_df], ignore_index=True)
full_df['Method'] = pd.Categorical(full_df['Method'], categories=['WGCNA', 'MEGENA', 'CPM'], ordered=True)

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

coverage = full_df.groupby('Method')['MONDO_ID'].nunique()
coverage.plot(kind='bar', ax=axes[0], color=['lightgreen', 'salmon', 'skyblue']) 
axes[0].set_title('Unique Disease Relationships Identified')
axes[0].set_ylabel('Count of MONDO IDs')


sns.boxplot(x='Method', y='neg_log_p', data=full_df, ax=axes[1], palette='pastel')
axes[1].set_title('Distribution of Significance (-log10 P-value)')
axes[1].set_ylabel('-log10(P-value)')

plt.tight_layout()
plt.savefig('performance_comparison.png')
print("Comparison graph saved as performance_comparison.png")

print("Summary Statistics:")
for method in ['WGCNA', 'MEGENA', 'CPM']:
    subset = full_df[full_df['Method'] == method]
    print(f"\n{method}:")
    print(f"  - Total significant enrichments: {len(subset)}")
    print(f"  - Unique diseases found: {subset['MONDO_ID'].nunique()}")
    print(f"  - Mean Significance (-log10): {subset['neg_log_p'].mean():.2f}")

print("Differential Analysis: ")
wgcna_diseases = set(full_df[full_df['Method'] == 'WGCNA']['MONDO_ID'].unique())
megena_diseases = set(full_df[full_df['Method'] == 'MEGENA']['MONDO_ID'].unique())
cpm_diseases = set(full_df[full_df['Method'] == 'CPM']['MONDO_ID'].unique())

# 2. Check for empty sets (good for debugging)
if not all([wgcna_diseases, megena_diseases, cpm_diseases]):
    print("Error: One or more method disease sets are empty.")

# 3. Define the labels (order must match the argument order)
method_labels = ('WGCNA', 'MEGENA', 'CPM')

# 4. Plot the Venn diagram
plt.figure(figsize=(10, 10))
v = venn3(
    subsets=[wgcna_diseases, megena_diseases, cpm_diseases],
    set_labels=method_labels,
    set_colors=('lightgreen', 'salmon', 'skyblue'), # Colors to match your bars
    alpha=0.6 # Transparency for overlap clarity
)

# Optional: Adjust label positions and size
plt.title("Overlap of Unique Diseases (MONDO IDs) Identified", fontsize=16)
plt.tight_layout()
plt.savefig('disease_overlap_venn.png')
print("Venn diagram saved as disease_overlap_venn.png")

