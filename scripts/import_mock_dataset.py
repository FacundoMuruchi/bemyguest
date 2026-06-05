import argparse
import json
import sys
from pathlib import Path

from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mongodb import mongo


DEFAULT_DATASET_PATH = PROJECT_ROOT / "mock_data" / "bemyguest_dataset_v1.json"


def parse_args():
    parser = argparse.ArgumentParser(description="Importa el mock dataset de BeMyGuest en MongoDB.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Ruta del archivo JSON fuente.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dataset_path = args.dataset
    if not dataset_path.is_absolute():
        dataset_path = PROJECT_ROOT / dataset_path

    try:
        mongo.client.admin.command("ping")
        counts = mongo.importar_dataset_json(dataset_path, reset_first=True)
    except FileNotFoundError:
        print(f"No se encontro el dataset: {dataset_path}", file=sys.stderr)
        return 1
    except (ValueError, json.JSONDecodeError) as error:
        print(f"Dataset invalido: {error}", file=sys.stderr)
        return 1
    except ServerSelectionTimeoutError:
        print("No se pudo conectar a MongoDB en localhost:27017.", file=sys.stderr)
        return 1
    except PyMongoError as error:
        print(f"Error importando datos en MongoDB: {error}", file=sys.stderr)
        return 1

    print(f"Dataset importado desde {dataset_path}")
    print(f"Total registros: {sum(counts.values())}")
    for collection_name, count in counts.items():
        print(f"- {collection_name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
