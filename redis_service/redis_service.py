# redis_service/redis_service.py
"""
Capa de abstracción que centraliza las operaciones del cliente de Redis.
Evita el acoplamiento directo entre la interfa de ui y el motor en memoria.
"""

import os
import redis

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)


def ping() -> bool:
    """Verifica si la conexión con el servidor de Redis está activa."""
    try:
        return r.ping()
    except Exception:
        return False


# Disponibilidad de habitaciones

def set_disponible(habitacion_id: str, disponible: bool):
    """
    Establece la disponibilidad de una habitación en Redis.
    "1" representa disponible, "0" representa no disponible.
    """
    key = f"habitacion:{habitacion_id}:disponible"
    value = "1" if disponible else "0"
    r.set(key, value)


def is_disponible(habitacion_id: str) -> bool:
    """
    Consulta la disponibilidad de una habitación en Redis.
    Retorna true solo si la llave existe y tiene el valor "1".
    """
    try:
        val = r.get(f"habitacion:{habitacion_id}:disponible")
        return val == "1"
    except Exception:
        return False


# Locking atómico para evitar overbooking

def adquirir_lock(habitacion_id: str, usuario_id: str, ttl_segundos: int = 600) -> bool:
    """
    Intenta adquirir un bloqueo atómico temporal sobre una habitación.
    Evita el overbooking si dos usuarios intentan reservar la misma habitación a la vez.

    Usa el parámetro atómico SETNX (nx=True) y expira automáticamente (ex=ttl).
    Retorna True si el lock fue adquirido con éxito, False si ya estaba bloqueada.
    """
    key = f"lock:habitacion:{habitacion_id}"
    
    #nx=True Le dice a Redis: "Crea esta llave únicamente si NO existe todavía"
    #Como Redis es mono-hilo, si la petición de A llega una millonésima de segundo antes que de B, Redis creará
    #  la llave para A y devolverá True. Cuando llegue la petición de B, la llave ya existirá,
    #  por lo que Redis rechazará la creación y devolverá None

    #ex=ttl_segundos:
    #la llave se autoeliminará de la memoria a los 10 minutos, liberando el bloqueo 
    # incluso si el proceso que lo adquirió falla o se queda colgado.

    exito = r.set(key, usuario_id, nx=True, ex=ttl_segundos)
    return bool(exito)


def liberar_lock(habitacion_id: str):
    """Libera el bloqueo sobre una habitación, permitiendo que otros la reserven."""
    r.delete(f"lock:habitacion:{habitacion_id}")


def get_lock_owner(habitacion_id: str) -> str | None:
    """
    Retorna el usuario_id que posee actualmente el bloqueo sobre la habitación.
    Retorna None si la habitación no está bloqueada.
    """
    return r.get(f"lock:habitacion:{habitacion_id}")


# Contadores    

def incrementar_reservas_hoy():
    """
    Incrementa atómicamente el contador de reservas exitosas diarias en Redis
    Configura una expiración de 24 horas si es una métrica nueva 
    """
    key = "stats:reservas:hoy"
    r.incr(key)
    r.expire(key, 86400)


def get_reservas_hoy() -> int:
    """Retorna el total de reservas realizadas hoy registradas en Redis."""
    try:
        val = r.get("stats:reservas:hoy")
        return int(val) if val else 0
    except Exception:
        return 0


# Seeding frontend

def seed_from_habitaciones(habitaciones: list) -> int:
    """
    Llena en batch las llaves de disponibilidad en Redis
    Retorna la cantidad de habitaciones cargadas exitosamente
    """
    pipe = r.pipeline()
    for hab in habitaciones:
        key = f"habitacion:{str(hab['_id'])}:disponible"
        value = "1" if hab.get("disponible", True) else "0"
        pipe.set(key, value)
    
    # metrica de reservas diarias inicializadas
    pipe.setnx("stats:reservas:hoy", "0")
    pipe.expire("stats:reservas:hoy", 86400)
    
    pipe.execute()
    return len(habitaciones)
