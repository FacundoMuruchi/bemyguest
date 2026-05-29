from uuid import uuid4

from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model

class BaseModel(Model):
    __abstract__ = True
    __keyspace__ = "bemyguest"

class HotelesPorPais(BaseModel):
    __table_name__ = "hoteles_por_pais"
   
    pais = columns.Text(partition_key=True)

    hotel_id = columns.Text(primary_key=True)

    nombre = columns.Text()

    ciudad = columns.Text()

    categoria = columns.Integer()

    calificacion_promedio = columns.Float()


class Hoteles(BaseModel):
    __table_name__ = "hotels"

    hotel_id = columns.Text(primary_key=True)

    nombre = columns.Text()

    ciudad = columns.Text()

    direccion = columns.Text()

    categoria = columns.Integer()

    calificacion_promedio = columns.Float()

class ResenasPorHotelFecha(BaseModel):
    __table_name__ = "resenas_por_hotel_fecha"

    hotel_id = columns.Text(partition_key=True)

    fecha = columns.Date(primary_key=True)

    resena_id = columns.Text(primary_key=True)

    usuario_id = columns.Text()

    comentario = columns.Text()

class CalifacionPorResena(BaseModel):
    __table_name__ = "califacion_por_resena"

    resena_id = columns.Text(partition_key=True)

    hotel_id = columns.Text(partition_key=True)

    calificacion_nombre = columns.Text(primary_key=True)

    puntuacion = columns.Integer()

class HabitacionesPorHotel(BaseModel):
    __table_name__ = "habitaciones_por_hotel"

    hotel_id = columns.Text(partition_key=True)

    habitacion_id = columns.Text(primary_key=True)

    numero = columns.Text()

    tipo = columns.Text()
    
    capacidad_adultos = columns.Integer()
    
    precio_por_noche = columns.Float()

class AmenitiesPorHabitacion(BaseModel):
    __table_name__ = "amenities_por_habitacion"

    hotel_id = columns.Text(partition_key=True)

    habitacion_id = columns.Text(partition_key=True)

    amenity_nombre = columns.Text(primary_key=True)

    descripcion = columns.Text()
