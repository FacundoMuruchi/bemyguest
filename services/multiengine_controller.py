from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from mongodb import mongo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_PATH = PROJECT_ROOT / "mock_data" / "bemyguest_dataset.json"


COLLECTIONS = {
    "Usuarios": mongo.col_usuarios,
    "Hoteles": mongo.col_hoteles,
    "Habitaciones": mongo.col_habitaciones,
    "Reservas": mongo.col_reservas,
    "Reseñas": mongo.col_resenas,
}

DATASET_KEYS = {
    "Usuarios": "usuarios",
    "Hoteles": "hoteles",
    "Habitaciones": "habitaciones",
    "Reservas": "reservas",
    "Reseñas": "resenas",
}

ID_PREFIXES = {
    "Usuarios": "USR",
    "Hoteles": "HOT",
    "Habitaciones": "HAB",
    "Reservas": "RSV",
    "Reseñas": "RES",
}


@dataclass
class EngineStatus:
    engine: str
    status: str
    detail: str


@dataclass
class OperationResult:
    action: str
    mongo_detail: str
    document_id: str | None = None
    counts: dict[str, Any] = field(default_factory=dict)
    engines: list[EngineStatus] = field(default_factory=list)

    @property
    def warnings(self) -> list[EngineStatus]:
        return [item for item in self.engines if item.status == "error"]

    def as_text(self) -> str:
        lines = [f"Mongo OK: {self.mongo_detail}"]
        for item in self.engines:
            prefix = item.status.upper()
            lines.append(f"{prefix} {item.engine}: {item.detail}")
        if self.counts:
            lines.append("")
            lines.append("Conteos:")
            for key, value in self.counts.items():
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)


def _safe_engine(result: OperationResult, engine: str, action: Callable[[], str | None]) -> None:
    try:
        detail = action() or "sincronizado"
    except Exception as error:
        result.engines.append(EngineStatus(engine, "error", str(error)))
    else:
        result.engines.append(EngineStatus(engine, "ok", detail))


def _skip_engine(result: OperationResult, engine: str, detail: str) -> None:
    result.engines.append(EngineStatus(engine, "skip", detail))


def _id(value: Any) -> str:
    return str(value)


def _doc_id(document: dict[str, Any]) -> str:
    return _id(document["_id"])


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _clean_for_mongo(document: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(document)


def _next_business_id(collection_name: str) -> str:
    collection = COLLECTIONS[collection_name]
    prefix = ID_PREFIXES[collection_name]
    pattern = f"^{prefix}[0-9]+$"
    cursor = collection.find({"_id": {"$regex": pattern}}, {"_id": 1})

    max_number = 0
    for document in cursor:
        raw_id = document.get("_id")
        if not isinstance(raw_id, str):
            continue
        try:
            number = int(raw_id[len(prefix):])
        except ValueError:
            continue
        max_number = max(max_number, number)

    return f"{prefix}{max_number + 1:04d}"


def _insert(collection_name: str, document: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    collection = COLLECTIONS[collection_name]
    mongo_document = _clean_for_mongo(document)
    if "_id" not in mongo_document:
        mongo_document["_id"] = _next_business_id(collection_name)
    inserted = collection.insert_one(mongo_document)
    mongo_document["_id"] = inserted.inserted_id
    return _id(inserted.inserted_id), mongo_document


def _delete_rows(rows: Any) -> int:
    count = 0
    for row in rows:
        row.delete()
        count += 1
    return count


def _load_dataset(dataset_path: Path) -> dict[str, Any]:
    with Path(dataset_path).open("r", encoding="utf-8") as file:
        return json.load(file)


def _sync_redis_create(result: OperationResult, collection_name: str, document: dict[str, Any]) -> None:
    if collection_name == "Habitaciones":
        def action() -> str:
            from redis_service import redis_service

            redis_service.set_disponible(_doc_id(document), bool(document.get("disponible", True)))
            return "disponibilidad de habitacion creada"

        _safe_engine(result, "Redis", action)
    elif collection_name == "Reservas":
        def action() -> str:
            from redis_service import redis_service

            estado = str(document.get("estado", ""))
            habitacion_id = _id(document["habitacion_id"])
            if estado == "confirmada":
                redis_service.set_disponible(habitacion_id, False)
                redis_service.liberar_lock(habitacion_id)
                redis_service.incrementar_reservas_hoy()
                return "habitacion marcada no disponible y contador incrementado"
            return "reserva no confirmada; Redis no cambia disponibilidad"

        _safe_engine(result, "Redis", action)
    else:
        _skip_engine(result, "Redis", f"{collection_name} no tiene proyeccion Redis")


def _sync_redis_delete(result: OperationResult, collection_name: str, document: dict[str, Any]) -> None:
    if collection_name != "Habitaciones":
        _skip_engine(result, "Redis", f"{collection_name} no tiene borrado Redis")
        return

    def action() -> str:
        from redis_service import redis_service

        habitacion_id = _doc_id(document)
        redis_service.r.delete(
            f"habitacion:{habitacion_id}:disponible",
            f"lock:habitacion:{habitacion_id}",
        )
        return "disponibilidad y lock eliminados"

    _safe_engine(result, "Redis", action)


def _sync_redis_delete_collection(result: OperationResult, collection_name: str) -> None:
    if collection_name != "Habitaciones":
        _skip_engine(result, "Redis", f"{collection_name} no tiene limpieza Redis")
        return

    def action() -> str:
        from redis_service import redis_service

        deleted = 0
        for pattern in ["habitacion:*:disponible", "lock:habitacion:*"]:
            keys = redis_service.r.keys(pattern)
            if keys:
                deleted += redis_service.r.delete(*keys)
        return f"{deleted} keys eliminadas"

    _safe_engine(result, "Redis", action)


def _sync_neo4j_create(result: OperationResult, collection_name: str, document: dict[str, Any]) -> None:
    def action() -> str:
        from implementacion_neo4j import neo4j_service

        driver = neo4j_service.get_driver()
        try:
            if collection_name == "Usuarios":
                neo4j_service.crear_usuario(
                    driver,
                    _doc_id(document),
                    document.get("nombre", ""),
                    document.get("apellido", ""),
                )
            elif collection_name == "Hoteles":
                neo4j_service.crear_hotel(
                    driver,
                    _doc_id(document),
                    document.get("nombre", ""),
                    document.get("ciudad", ""),
                    document.get("pais", ""),
                    int(document.get("categoria", 0) or 0),
                )
            elif collection_name == "Habitaciones":
                neo4j_service.crear_habitacion(
                    driver,
                    _doc_id(document),
                    document.get("numero", ""),
                    document.get("tipo", ""),
                    float(document.get("precio_por_noche", 0.0) or 0.0),
                )
                neo4j_service.crear_relacion_habitacion_hotel(
                    driver,
                    _doc_id(document),
                    _id(document["hotel_id"]),
                )
            elif collection_name == "Reservas":
                neo4j_service.crear_relacion_reserva(
                    driver,
                    _id(document["usuario_id"]),
                    _id(document["hotel_id"]),
                    str(document.get("fecha_reserva", "")),
                    int(document.get("noches", 0) or 0),
                    str(document.get("estado", "")),
                )
            elif collection_name == "Reseñas":
                puntaje = document.get("calificacion", {}).get("general", 0.0)
                neo4j_service.crear_relacion_calificacion(
                    driver,
                    _id(document["usuario_id"]),
                    _id(document["hotel_id"]),
                    float(puntaje or 0.0),
                    str(document.get("fecha", "")),
                )
            else:
                return "sin proyeccion Neo4j"
        finally:
            driver.close()
        return "grafo actualizado"

    _safe_engine(result, "Neo4j", action)


def _sync_neo4j_delete(result: OperationResult, collection_name: str, document: dict[str, Any]) -> None:
    def action() -> str:
        from implementacion_neo4j import neo4j_service

        driver = neo4j_service.get_driver()
        try:
            with driver.session() as session:
                if collection_name == "Usuarios":
                    session.run("MATCH (u:Usuario {id: $id}) DETACH DELETE u", id=_doc_id(document))
                elif collection_name == "Hoteles":
                    session.run("MATCH (h:Hotel {id: $id}) DETACH DELETE h", id=_doc_id(document))
                elif collection_name == "Habitaciones":
                    session.run("MATCH (h:Habitacion {id: $id}) DETACH DELETE h", id=_doc_id(document))
                elif collection_name == "Reservas":
                    session.run(
                        """
                        MATCH (:Usuario {id: $usuario_id})-[r:RESERVO {fecha_reserva: $fecha_reserva}]->(:Hotel {id: $hotel_id})
                        DELETE r
                        """,
                        usuario_id=_id(document["usuario_id"]),
                        hotel_id=_id(document["hotel_id"]),
                        fecha_reserva=str(document.get("fecha_reserva", "")),
                    )
                elif collection_name == "Reseñas":
                    session.run(
                        """
                        MATCH (:Usuario {id: $usuario_id})-[r:CALIFICO {fecha: $fecha}]->(:Hotel {id: $hotel_id})
                        DELETE r
                        """,
                        usuario_id=_id(document["usuario_id"]),
                        hotel_id=_id(document["hotel_id"]),
                        fecha=str(document.get("fecha", "")),
                    )
                else:
                    return "sin borrado Neo4j"
        finally:
            driver.close()
        return "grafo actualizado"

    _safe_engine(result, "Neo4j", action)


def _sync_neo4j_delete_collection(result: OperationResult, collection_name: str) -> None:
    def action() -> str:
        from implementacion_neo4j import neo4j_service

        label_by_collection = {
            "Usuarios": "Usuario",
            "Hoteles": "Hotel",
            "Habitaciones": "Habitacion",
        }
        driver = neo4j_service.get_driver()
        try:
            with driver.session() as session:
                if collection_name in label_by_collection:
                    label = label_by_collection[collection_name]
                    session.run(f"MATCH (n:{label}) DETACH DELETE n")
                elif collection_name == "Reservas":
                    session.run("MATCH ()-[r:RESERVO]->() DELETE r")
                elif collection_name == "Reseñas":
                    session.run("MATCH ()-[r:CALIFICO]->() DELETE r")
                else:
                    return "sin limpieza Neo4j"
        finally:
            driver.close()
        return "grafo actualizado"

    _safe_engine(result, "Neo4j", action)


def _sync_cassandra_create(result: OperationResult, collection_name: str, document: dict[str, Any]) -> None:
    if collection_name in {"Usuarios", "Reservas"}:
        _skip_engine(result, "Cassandra", f"{collection_name} no tiene tabla query-driven actual")
        return

    def action() -> str:
        from cassandradb.cassandra import crear_tablas
        from cassandradb.models import (
            AmenitiesPorHabitacion,
            CalifacionPorResena,
            HabitacionesPorHotel,
            HotelesPorPais,
            ResenasPorHotelFecha,
        )

        crear_tablas()
        if collection_name == "Hoteles":
            HotelesPorPais.create(
                pais=str(document.get("pais", "")),
                hotel_id=_doc_id(document),
                nombre=str(document.get("nombre", "")),
                ciudad=str(document.get("ciudad", "")),
                categoria=int(document.get("categoria", 0) or 0),
                calificacion_promedio=float(document.get("calificacion_promedio", 0.0) or 0.0),
            )
        elif collection_name == "Habitaciones":
            HabitacionesPorHotel.create(
                hotel_id=_id(document["hotel_id"]),
                habitacion_id=_doc_id(document),
                numero=str(document.get("numero", "")),
                tipo=str(document.get("tipo", "")),
                capacidad_adultos=int(document.get("capacidad_adultos", 0) or 0),
                precio_por_noche=float(document.get("precio_por_noche", 0.0) or 0.0),
            )
            for nombre, valor in document.get("amenities", {}).items():
                AmenitiesPorHabitacion.create(
                    hotel_id=_id(document["hotel_id"]),
                    habitacion_id=_doc_id(document),
                    amenity_nombre=str(nombre),
                    descripcion=str(valor),
                )
        elif collection_name == "Reseñas":
            ResenasPorHotelFecha.create(
                hotel_id=_id(document["hotel_id"]),
                fecha=_to_date(document["fecha"]),
                resena_id=_doc_id(document),
                usuario_id=_id(document["usuario_id"]),
                comentario=str(document.get("comentario", "")),
            )
            for nombre, puntuacion in document.get("calificacion", {}).items():
                CalifacionPorResena.create(
                    hotel_id=_id(document["hotel_id"]),
                    resena_id=_doc_id(document),
                    calificacion_nombre=str(nombre),
                    puntuacion=int(puntuacion),
                )
        return "tablas query-driven actualizadas"

    _safe_engine(result, "Cassandra", action)


def _sync_cassandra_delete(result: OperationResult, collection_name: str, document: dict[str, Any]) -> None:
    if collection_name in {"Usuarios", "Reservas"}:
        _skip_engine(result, "Cassandra", f"{collection_name} no tiene tabla query-driven actual")
        return

    def action() -> str:
        from cassandradb.models import (
            AmenitiesPorHabitacion,
            CalifacionPorResena,
            HabitacionesPorHotel,
            HotelesPorPais,
            ResenasPorHotelFecha,
        )

        deleted = 0
        if collection_name == "Hoteles":
            deleted += _delete_rows(
                HotelesPorPais.objects.filter(
                    pais=str(document.get("pais", "")),
                    hotel_id=_doc_id(document),
                )
            )
        elif collection_name == "Habitaciones":
            deleted += _delete_rows(
                HabitacionesPorHotel.objects.filter(
                    hotel_id=_id(document["hotel_id"]),
                    habitacion_id=_doc_id(document),
                )
            )
            deleted += _delete_rows(
                AmenitiesPorHabitacion.objects.filter(
                    hotel_id=_id(document["hotel_id"]),
                    habitacion_id=_doc_id(document),
                )
            )
        elif collection_name == "Reseñas":
            deleted += _delete_rows(
                ResenasPorHotelFecha.objects.filter(
                    hotel_id=_id(document["hotel_id"]),
                    fecha=_to_date(document["fecha"]),
                    resena_id=_doc_id(document),
                )
            )
            deleted += _delete_rows(
                CalifacionPorResena.objects.filter(
                    hotel_id=_id(document["hotel_id"]),
                    resena_id=_doc_id(document),
                )
            )
        return f"{deleted} filas eliminadas"

    _safe_engine(result, "Cassandra", action)


def _sync_cassandra_delete_collection(result: OperationResult, collection_name: str) -> None:
    def action() -> str:
        from cassandradb.cassandra import eliminar_todos_documentos
        from cassandradb.models import (
            AmenitiesPorHabitacion,
            CalifacionPorResena,
            HabitacionesPorHotel,
            HotelesPorPais,
            ResenasPorHotelFecha,
        )

        models_by_collection = {
            "Hoteles": [HotelesPorPais],
            "Habitaciones": [HabitacionesPorHotel, AmenitiesPorHabitacion],
            "Reseñas": [ResenasPorHotelFecha, CalifacionPorResena],
        }
        models = models_by_collection.get(collection_name, [])
        if not models:
            return f"{collection_name} no tiene tabla query-driven actual"
        for model in models:
            eliminar_todos_documentos(model)
        return "tablas query-driven limpiadas"

    _safe_engine(result, "Cassandra", action)


def create_usuario(document: dict[str, Any]) -> OperationResult:
    return _create_document("Usuarios", document)


def create_hotel(document: dict[str, Any]) -> OperationResult:
    return _create_document("Hoteles", document)


def create_habitacion(document: dict[str, Any]) -> OperationResult:
    return _create_document("Habitaciones", document)


def create_reserva(document: dict[str, Any]) -> OperationResult:
    return _create_document("Reservas", document)


def create_resena(document: dict[str, Any]) -> OperationResult:
    return _create_document("Reseñas", document)


def _create_document(collection_name: str, document: dict[str, Any]) -> OperationResult:
    inserted_id, inserted_document = _insert(collection_name, document)
    result = OperationResult(
        action=f"create_{collection_name}",
        mongo_detail=f"documento creado en {collection_name} con _id {inserted_id}",
        document_id=inserted_id,
    )
    _sync_redis_create(result, collection_name, inserted_document)
    _sync_neo4j_create(result, collection_name, inserted_document)
    _sync_cassandra_create(result, collection_name, inserted_document)
    return result


def delete_document(collection_name: str, document: dict[str, Any]) -> OperationResult:
    deleted = COLLECTIONS[collection_name].delete_one({"_id": document["_id"]})
    result = OperationResult(
        action=f"delete_{collection_name}",
        mongo_detail=f"{deleted.deleted_count} documento eliminado de {collection_name}",
        document_id=_doc_id(document),
    )
    if deleted.deleted_count:
        _sync_redis_delete(result, collection_name, document)
        _sync_neo4j_delete(result, collection_name, document)
        _sync_cassandra_delete(result, collection_name, document)
    return result


def delete_collection(collection_name: str) -> OperationResult:
    deleted = mongo.eliminar_todos_documentos(COLLECTIONS[collection_name])
    result = OperationResult(
        action=f"delete_collection_{collection_name}",
        mongo_detail=f"{deleted.deleted_count} documentos eliminados de {collection_name}",
    )
    _sync_redis_delete_collection(result, collection_name)
    _sync_neo4j_delete_collection(result, collection_name)
    _sync_cassandra_delete_collection(result, collection_name)
    return result


def import_dataset_to_all(dataset_path: Path = DEFAULT_DATASET_PATH, reset_first: bool = True) -> OperationResult:
    dataset = _load_dataset(dataset_path)
    counts = mongo.validar_dataset(dataset)

    if reset_first:
        for collection in mongo.DATASET_COLLECTIONS.values():
            mongo.eliminar_todos_documentos(collection)

    for key, collection in mongo.DATASET_COLLECTIONS.items():
        collection.insert_many(deepcopy(dataset[key]))

    result = OperationResult(
        action="import_dataset_to_all",
        mongo_detail=f"dataset importado desde {dataset_path}",
        counts={f"mongo.{key}": value for key, value in counts.items()},
    )

    _safe_engine(
        result,
        "Redis",
        lambda: _import_dataset_to_redis(dataset),
    )
    _safe_engine(
        result,
        "Neo4j",
        lambda: _import_dataset_to_neo4j(dataset_path),
    )
    _safe_engine(
        result,
        "Cassandra",
        lambda: _import_dataset_to_cassandra(dataset_path),
    )
    return result


def _import_dataset_to_redis(dataset: dict[str, Any]) -> str:
    from redis_service import redis_service

    count = redis_service.seed_from_habitaciones(dataset.get("habitaciones", []))
    return f"{count} habitaciones sincronizadas"


def _import_dataset_to_neo4j(dataset_path: Path) -> str:
    from implementacion_neo4j import neo4j_service

    counts = neo4j_service.importar_dataset(dataset_path, reset=True)
    return f"{sum(counts.values())} elementos de grafo importados"


def _import_dataset_to_cassandra(dataset_path: Path) -> str:
    from cassandradb.cassandra import importar_dataset_json

    counts = importar_dataset_json(dataset_path, reset_first=True)
    return f"{sum(counts.values())} filas query-driven importadas"
