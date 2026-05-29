# redis_service/redis_service.py
"""
Capa de abstracción que centraliza las operaciones del cliente de Redis.
Evita el acoplamiento directo entre la interfaz de UI y el motor en memoria.
"""

import os
import redis

# Conexión directa y global al cliente de Redis
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


# ── DISPONIBILIDAD DE HABITACIONES ────────────────────────────────────────────

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
    Retorna True solo si la llave existe y tiene el valor "1".
    """
    try:
        val = r.get(f"habitacion:{habitacion_id}:disponible")
        return val == "1"
    except Exception:
        return False


# ── LOCKING ATÓMICO (ANTI-OVERBOOKING) ────────────────────────────────────────

def adquirir_lock(habitacion_id: str, usuario_id: str, ttl_segundos: int = 600) -> bool:
    """
    Intenta adquirir un bloqueo atómico temporal sobre una habitación.
    Evita el overbooking si dos usuarios intentan reservar la misma habitación a la vez.

    Usa el parámetro atómico SETNX (nx=True) y expira automáticamente (ex=ttl).
    Retorna True si el lock fue adquirido con éxito, False si ya estaba bloqueada.
    """
    key = f"lock:habitacion:{habitacion_id}"
    # set() con nx=True retorna True si crea la llave, None si ya existe
    exito = r.set(key, usuario_id, nx=True, ex=ttl_segundos)
    return bool(exito)


def liberar_lock(habitacion_id: str):
    """Libera el bloqueo sobre una habitación, permitiendo que otros la reserven."""
    r.delete(f"lock:habitacion:{habitacion_id}")


def get_lock_owner(habitacion_id: str) -> str | None:
    """
    Retorna el usuario_id (string) que posee actualmente el bloqueo sobre la habitación.
    Retorna None si la habitación no está bloqueada.
    """
    return r.get(f"lock:habitacion:{habitacion_id}")


# ── MÉTRICAS DE NEGOCIO (CONTADORES RÁPIDOS) ──────────────────────────────────

def incrementar_reservas_hoy():
    """
    Incrementa atómicamente el contador de reservas exitosas diarias en Redis.
    Configura una expiración de 24 horas (86400s) si es una nueva métrica.
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


# ── SEEDING DESDE FRONTEND ───────────────────────────────────────────────────

def seed_from_habitaciones(habitaciones: list) -> int:
    """
    Puebla en lote (Pipeline) las llaves de disponibilidad en Redis.
    Retorna la cantidad de habitaciones cargadas exitosamente.
    """
    pipe = r.pipeline()
    for hab in habitaciones:
        key = f"habitacion:{str(hab['_id'])}:disponible"
        value = "1" if hab.get("disponible", True) else "0"
        pipe.set(key, value)
    
    # Aseguramos que la métrica de reservas diarias esté inicializada
    pipe.setnx("stats:reservas:hoy", "0")
    pipe.expire("stats:reservas:hoy", 86400)
    
    pipe.execute()
    return len(habitaciones)
