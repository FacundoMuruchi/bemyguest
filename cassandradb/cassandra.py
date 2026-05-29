import json

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
            fecha=resena["fecha"],
            resena_id=resena["_id"],
            usuario_id=resena["usuario_id"],
            comentario=resena["comentario"],
        )

        for calificacion_nombre, puntuacion in resena["calificacion"].items():

            CalifacionPorResena.create(
                resena_id=resena["_id"],
                hotel_id=resena["hotel_id"],
                calificacion_nombre=calificacion_nombre,
                puntuacion=puntuacion
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
            precio_por_noche=float(
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

