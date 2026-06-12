import json

from datetime import date, datetime
from pathlib import Path

from cassandra.cqlengine.management import sync_table
from cassandra.cqlengine.management import drop_table

from .config import *

from .models import (
    HotelesPorPais,
    ResenasPorHotelFecha,
    CalifacionPorResena,
    HabitacionesPorHotel,
    AmenitiesPorHabitacion,
)

DATASET_MODELS = {
    "hoteles_por_pais": HotelesPorPais,
    "resenas_por_hotel_fecha": ResenasPorHotelFecha,
    "calificaciones_por_resena": CalifacionPorResena,
    "habitaciones_por_hotel": HabitacionesPorHotel,
    "amenities_por_habitacion": AmenitiesPorHabitacion,
}

def crear_tablas():
    for modelo in DATASET_MODELS.values():
        print(modelo.column_family_name())
        sync_table(modelo)

    print("Tablas sincronizadas.")


def mostrar_documentos(nombre, documentos):

    print(f"{nombre.upper():-^100}")

    for doc in documentos:

        print(doc)


def insertar_documento(modelo, documento):

    return modelo.create(**documento)


def to_text(value):

    return str(value)


def to_int(value, default=0):

    if value in (None, ""):
        return default

    return int(value)


def to_float(value, default=0.0):

    if value in (None, ""):
        return default

    return float(value)


def to_date(value):

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


def registrar_hotel(documento):

    hotel_id = to_text(documento["_id"])
    HotelesPorPais.create(
        pais=to_text(documento.get("pais", "")),
        hotel_id=hotel_id,
        nombre=to_text(documento.get("nombre", "")),
        ciudad=to_text(documento.get("ciudad", "")),
        categoria=to_int(documento.get("categoria")),
        calificacion_promedio=to_float(
            documento.get("calificacion_promedio")
        ),
    )

    return ["hoteles_por_pais"]


def registrar_habitacion(documento):

    hotel_id = to_text(documento["hotel_id"])
    habitacion_id = to_text(documento["_id"])

    HabitacionesPorHotel.create(
        hotel_id=hotel_id,
        habitacion_id=habitacion_id,
        numero=to_text(documento.get("numero", "")),
        tipo=to_text(documento.get("tipo", "")),
        capacidad_adultos=to_int(
            documento.get("capacidad_adultos")
        ),
        precio_por_noche=to_float(
            documento.get("precio_por_noche")
        ),
    )

    for nombre, valor in documento.get("amenities", {}).items():
        AmenitiesPorHabitacion.create(
            habitacion_id=habitacion_id,
            hotel_id=hotel_id,
            amenity_nombre=to_text(nombre),
            descripcion=to_text(valor)
        )

    return ["habitaciones_por_hotel", "amenities_por_habitacion"]


def registrar_resena(documento):

    hotel_id = to_text(documento["hotel_id"])
    resena_id = to_text(documento["_id"])

    ResenasPorHotelFecha.create(
        hotel_id=hotel_id,
        fecha=to_date(documento["fecha"]),
        resena_id=resena_id,
        usuario_id=to_text(documento["usuario_id"]),
        comentario=to_text(documento.get("comentario", "")),
    )

    for calificacion_nombre, puntuacion in documento.get("calificacion", {}).items():
        CalifacionPorResena.create(
            resena_id=resena_id,
            hotel_id=hotel_id,
            calificacion_nombre=to_text(calificacion_nombre),
            puntuacion=to_int(puntuacion)
        )

    return ["resenas_por_hotel_fecha", "calificacion_por_resena"]


def registrar_documento_en_cassandra(coleccion, documento):

    registradores = {
        "Hoteles": registrar_hotel,
        "Habitaciones": registrar_habitacion,
        "Reseñas": registrar_resena,
    }

    registrador = registradores.get(coleccion)

    if not registrador:
        return []

    return registrador(documento)


def eliminar_todos_documentos(modelo):

    for row in modelo.objects.all():

        row.delete()


def cargar_dataset_json(path):

    dataset_path = Path(path)

    with dataset_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def validar_dataset(dataset):

    for key in DATASET_MODELS:

        if key not in dataset:

            raise ValueError(
                f"Falta la coleccion '{key}'"
            )

        if not isinstance(dataset[key], list):

            raise ValueError(
                f"La coleccion '{key}' debe ser lista"
            )

    return {
        key: len(dataset[key])
        for key in DATASET_MODELS
    }


def importar_dataset_json(
    path,
    reset_first=True
):

    dataset = cargar_dataset_json(path)

    if reset_first:
        for modelo in DATASET_MODELS.values():
            eliminar_todos_documentos(modelo)


    for hotel in dataset["hoteles"]:

        HotelesPorPais.create(
            pais=hotel["pais"],
            hotel_id=hotel["_id"],
            nombre=hotel["nombre"],
            ciudad=hotel["ciudad"],
            categoria=hotel["categoria"],
            calificacion_promedio=hotel["calificacion_promedio"]
        )


    for resena in dataset["resenas"]:

        ResenasPorHotelFecha.create(
            hotel_id=resena["hotel_id"],
            fecha=to_date(resena["fecha"]),
            resena_id=resena["_id"],
            usuario_id=resena["usuario_id"],
            comentario=resena["comentario"],
        )

        for calificacion_nombre, puntuacion in resena["calificacion"].items():

            CalifacionPorResena.create(
                resena_id=resena["_id"],
                hotel_id=resena["hotel_id"],
                calificacion_nombre=calificacion_nombre,
                puntuacion=to_int(puntuacion)
            )



    for habitacion in dataset["habitaciones"]:
        HabitacionesPorHotel.create(
            hotel_id=habitacion["hotel_id"],
            habitacion_id=habitacion["_id"],
            numero=habitacion["numero"],
            tipo=habitacion["tipo"],
            capacidad_adultos=habitacion[
                "capacidad_adultos"
            ],
            precio_por_noche=to_float(
                habitacion["precio_por_noche"]
            ),
        )

        for nombre, valor in habitacion["amenities"].items():
            AmenitiesPorHabitacion.create(
                habitacion_id=habitacion["_id"],
                hotel_id=habitacion["hotel_id"],
                amenity_nombre=nombre,
                descripcion=str(valor)
            )

    return {
        "hoteles_por_pais":
            HotelesPorPais.objects.count(),

        "resenas_por_hotel_fecha":
            ResenasPorHotelFecha.objects.count(),

        "calificacion_por_resena":
            CalifacionPorResena.objects.count(),

        "habitaciones_por_hotel":
            HabitacionesPorHotel.objects.count(),

        "amenities_por_habitacion":
            AmenitiesPorHabitacion.objects.count(),
    }

def obtener_hoteles_por_pais(
    pais
):

    return list(
        HotelesPorPais.objects.filter(
            pais=pais
        )
    )


def obtener_resenas_por_hotel(
    hotel_id
):

    return list(
        ResenasPorHotelFecha.objects.filter(
            hotel_id=hotel_id
        )
    )

def obtener_calificaciones_por_resena(
    resena_id,
    hotel_id
):

    return list(
        CalifacionPorResena.objects.filter(
            resena_id=resena_id,
            hotel_id=hotel_id
        )
    )


def obtener_habitaciones_por_hotel(
    hotel_id,
):

    return list(
        HabitacionesPorHotel.objects.filter(
            hotel_id=hotel_id
        )
    )


def obtener_amenities_por_habitacion(
    habitacion_id,
    hotel_id
):

    return list(
        AmenitiesPorHabitacion.objects.filter(
            habitacion_id=habitacion_id,
            hotel_id=hotel_id
        )
    )
