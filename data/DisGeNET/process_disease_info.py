import json
import os

def process_disease_info(file_path):
    gene = file_path.split("/")[-1].split("_")[0]
    with open(f"data/{gene}_disease_info.json", "r") as f:
        data = json.load(f)
    if data["paging"]["totalElements"] == 0:
        print(f"No disease associations found for {gene}")
        return None
    diseases = []
    for result in data["payload"]:
        disease_info = {
            "diseaseName": result.get("diseaseName", ""),
            "diseaseVocabularies": result.get("diseaseVocabularies", ""),
            "score": result.get("score", 0)
        }
        diseases.append(disease_info)
    return diseases

if __name__ == "__main__":
    null_genes = 0
    with open("gene_disease_associations.json", "w") as f:
        gene_disease_associations = {}
        for file in os.listdir("data"):
            if file.endswith("_disease_info.json"):
                print(f"Processing {file}")
                diseases = process_disease_info(os.path.join("data", file))
                if diseases is not None:
                    gene = file.split("_")[0]
                    gene_disease_associations[gene] = diseases
                else:
                    null_genes += 1
        print(f"Number of Total genes processed: {len(gene_disease_associations) + null_genes}")
        print(f"Number of genes with no disease associations: {null_genes}")
        json.dump(gene_disease_associations, f, indent=4)