import json
from scipy.stats import hypergeom

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

disease_dict = load_json('data/DisGeNET/disease_gene_relationships.json')
wgcna_modules = load_json('wgcna_modules.json')
megena_modules = load_json('megena_modules.json')

all_genes = set()
for mod in wgcna_modules.values(): all_genes.update(mod)
bg_count = len(all_genes)

wgcna_results = run_enrichment(disease_dict, wgcna_modules, bg_count)
megena_results = run_enrichment(disease_dict, megena_modules, bg_count)

with open('evaluation_results.json', 'w') as f:
    json.dump({"WGCNA": wgcna_results, "MEGENA": megena_results}, f, indent=4)