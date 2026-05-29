# redis_service/redis_service.py
import os
import redis

# Conectamos directamente al cliente de Redis usando variables de entorno o localhost
r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)


def ping():
    try:
        return r.ping()
    except Exception:
        return False


# --- DISPONIBILIDAD ---

def set_disponible(habitacion_id, disponible):
    # Guardamos "1" para disponible y "0" para ocupado
    valor = "1" if disponible else "0"
    r.set(f"habitacion:{habitacion_id}:disponible", valor)


def is_disponible(habitacion_id):
    val = r.get(f"habitacion:{habitacion_id}:disponible")
    return val == "1"


# --- LOCKS TEMPORALES (Pessimistic Locking) ---

def adquirir_lock(habitacion_id, usuario_id):
    # Intentamos crear la key del lock por 10 minutos (600 segundos)
    # nx=True hace que solo se cree si NO existe (evita overbooking)
    return r.set(f"lock:habitacion:{habitacion_id}", usuario_id, nx=True, ex=600)


def liberar_lock(habitacion_id):
    r.delete(f"lock:habitacion:{habitacion_id}")


def get_lock_owner(habitacion_id):
    return r.get(f"lock:habitacion:{habitacion_id}")


# --- CONTADORES Y MÉTRICAS ---

def incrementar_reservas_hoy():
    # Suma 1 al contador diario y le pone vencimiento de 24 horas
    r.incr("stats:reservas:hoy")
    r.expire("stats:reservas:hoy", 86400)


def get_reservas_hoy():
    val = r.get("stats:reservas:hoy")
    if val:
        return int(val)
    return 0


# --- CARGA INICIAL (SEED) ---

def seed_from_habitaciones(habitaciones):
    # Recorremos la lista de Mongo y guardamos cada estado en Redis
    for hab in habitaciones:
        hab_id = str(hab["_id"])
        valor = "1" if hab.get("disponible", True) else "0"
        r.set(f"habitacion:{hab_id}:disponible", valor)
        
    # Inicializamos el contador de hoy
    r.setnx("stats:reservas:hoy", "0")
    r.expire("stats:reservas:hoy", 86400)
    
    return len(habitaciones)
