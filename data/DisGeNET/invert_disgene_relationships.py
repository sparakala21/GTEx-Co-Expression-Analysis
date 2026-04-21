import json

def invert_relationships(input_file, output_file):
    with open(input_file, 'r') as f:
        data = json.load(f)

    disease_dict = {}

    for gene, disease_list in data.items():
        for entry in disease_list:
            name = entry["diseaseName"]
            vocabularies = entry["diseaseVocabularies"]
            
            mondo_id = next((v for v in vocabularies if v.startswith("MONDO")), None)
            
            if mondo_id:
                if mondo_id not in disease_dict:
                    disease_dict[mondo_id] = {
                        "diseaseName": name,
                        "genes": set() 
                    }
                disease_dict[mondo_id]["genes"].add(gene)

    for mid in disease_dict:
        disease_dict[mid]["genes"] = list(disease_dict[mid]["genes"])

    with open(output_file, 'w') as f:
        json.dump(disease_dict, f, indent=4)

if __name__ == "__main__":
    input_file = 'gene_disease_associations.json'
    output_file = 'disease_gene_relationships.json'
    invert_relationships(input_file, output_file)