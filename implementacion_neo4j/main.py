"""
Importa el dataset completo a Neo4j.
Uso: uv run python neo4j/main.py
"""

from pathlib import Path

try:
    from .neo4j_service import importar_dataset
except ImportError:
    from neo4j_service import importar_dataset


dataset_path = Path(__file__).resolve().parents[1] / "mock_data" / "bemyguest_dataset.json"

counts = importar_dataset(dataset_path, reset=True)

print(f"Dataset importado desde {dataset_path}")
print(f"Total registros: {sum(counts.values())}")
for entidad, count in counts.items():
    print(f"  - {entidad}: {count}")
