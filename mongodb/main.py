from pathlib import Path

try:
    from .mongo import *
except:
    from mongo import *


dataset_path = Path(__file__).resolve().parents[1] / "mock_data" / "bemyguest_dataset.json"
counts = importar_dataset_json(dataset_path, reset_first=True)

print(f"Dataset importado desde {dataset_path}")
print(f"Total registros: {sum(counts.values())}")
for collection_name, count in counts.items():
    print(f"- {collection_name}: {count}")
