import json
from pathlib import Path

try:
    from .config import *
except:
    from config import *


ESTADOS = ["confirmada", "pendiente", "cancelada"]

DATASET_COLLECTIONS = {
    "usuarios": col_usuarios,
    "hoteles": col_hoteles,
    "habitaciones": col_habitaciones,
    "reservas": col_reservas,
    "resenas": col_reseñas,
}


def crear_coleccion(nombre):
    if nombre not in db.list_collection_names():
        db.create_collection(nombre)
    return db[nombre]


def mostrar_documentos(documentos):
    nombre_col = documentos.collection.name.upper()
    print(f"{nombre_col:-^100}")

    for doc in documentos:
        print(doc)


def insertar_documento(collection, documento):
    return collection.insert_one(documento)


def eliminar_documento(collection, criterio):
    return collection.delete_one(criterio)


def eliminar_todos_documentos(collection):
    return collection.delete_many({})


def cargar_dataset_json(path):
    dataset_path = Path(path)
    with dataset_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validar_dataset(dataset):
    for key in DATASET_COLLECTIONS:
        if key not in dataset:
            raise ValueError(f"Falta la coleccion '{key}' en el dataset.")
        if not isinstance(dataset[key], list):
            raise ValueError(f"La coleccion '{key}' debe ser una lista.")
        if not dataset[key]:
            raise ValueError(f"La coleccion '{key}' no puede estar vacia.")

    return {key: len(dataset[key]) for key in DATASET_COLLECTIONS}


def importar_dataset_json(path, reset_first=True):
    dataset = cargar_dataset_json(path)
    counts = validar_dataset(dataset)

    if reset_first:
        for collection in DATASET_COLLECTIONS.values():
            eliminar_todos_documentos(collection)

    for key, collection in DATASET_COLLECTIONS.items():
        collection.insert_many(dataset[key])

    return counts
