"""
Pobla Redis con el estado de disponibilidad de las habitaciones
leyendo los documentos reales de MongoDB.

Uso:
    uv run redis_service/seed_redis.py
    uv run redis_service/seed_redis.py --reset  # limpia Redis antes de cargar
    uv run redis_service/seed_redis.py --dry-run  # muestra las keys sin escribir
"""

import argparse
import os
import sys

import redis
from pymongo import MongoClient

# Conexión

MONGO_URI= os.getenv("MONGO_URI",   "mongodb://localhost:27017")
REDIS_HOST= os.getenv("REDIS_HOST",  "localhost")
REDIS_PORT= int(os.getenv("REDIS_PORT", 6379))
DB_NAME= "bemyguest"


def get_mongo():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")# falla rápido si no hay conexión
    return client[DB_NAME]


def get_redis():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    return r


# Dataset de fallback (sin mongo)
# Útiles para pruebas unitarias cuando mongo no está disponible.

FALLBACK_HABITACIONES = [
    {"_id": "aaa000000000000000000001", "numero": "101", "tipo": "estandar",  "disponible": True},
    {"_id": "aaa000000000000000000002", "numero": "102", "tipo": "estandar",  "disponible": True},
    {"_id": "aaa000000000000000000003", "numero": "201", "tipo": "superior",  "disponible": False},
    {"_id": "aaa000000000000000000004", "numero": "202", "tipo": "superior",  "disponible": True},
    {"_id": "aaa000000000000000000005", "numero": "301", "tipo": "suite",     "disponible": False},
    {"_id": "aaa000000000000000000006", "numero": "302", "tipo": "suite",     "disponible": True},
    {"_id": "aaa000000000000000000007", "numero": "401", "tipo": "cabaña",    "disponible": True},
    {"_id": "aaa000000000000000000008", "numero": "402", "tipo": "cabaña",    "disponible": False},
]


# Lógica de seeding 

def construir_entradas(habitaciones: list) -> list[tuple[str, str]]:
    """Devuelve lista de (key, value) para disponibilidad.

    La key sigue el formato: habitacion:{id}:disponible
    El value es "1" para disponible y "0" para no disponible.
    """
    entries = []

    #Cada diccionario representa una habitación traída de MongoDB o del dataset de fallback.
    for h in habitaciones:
        hab_id = str(h["_id"])
        valor  = "1" if h.get("disponible", True) else "0"
        entries.append((f"habitacion:{hab_id}:disponible", valor))
    return entries


def seed(r: redis.Redis, entries: list[tuple[str, str]], dry_run: bool):
    """Escribe las keys de disponibilidad en Redis usando pipeline para eficiencia."""
    
    if dry_run:
        print("\n[DRY-RUN] Keys que se escribirían en Redis:")
        for key, val in entries:
            estado = "disponible" if val == "1" else "no disponible"
            print(f"  SET {key!r:60s} -> {val}  ({estado})")
        print(f"\nTotal: {len(entries)} keys")
        return

    #Si no es una simulación, crea un Pipeline
    #En lugar de enviar un comando a la base de datos por cada habitación (muchos idas y vueltas en la red), 
    # el Pipeline acumula todos los comandos SET en memoria local.
    pipe = r.pipeline()
    for key, val in entries:
        pipe.set(key, val)

    # Inicializar contador de reservas de hoy si no existe
    pipe.setnx("stats:reservas:hoy", "0")
    pipe.expire("stats:reservas:hoy", 86400) # Expira en 24 horas

    pipe.execute()
    print(f"{len(entries)} keys de disponibilidad cargadas en Redis.")
    print(f"stats:reservas:hoy inicializado.")


def reset_redis(r: redis.Redis):
    """Elimina TODAS las keys en Redis que sean del dataset BeMyGuest."""
    patterns = [
        "habitacion:*:disponible",
        "lock:habitacion:*",
        "sesion:*",
        "stats:reservas:*",
    ]
    eliminadas = 0
    for pattern in patterns:
        keys = r.keys(pattern)
        if keys:
            eliminadas += r.delete(*keys)
    print(f"[RESET] {eliminadas} keys eliminadas de Redis.")


# Main

def main():
    """
        Se encarga de procesar los parámetros que ingresas por consola, controlar las conexiones a las bases de datos y mandar a ejecutar las tareas de limpieza y 
        escritura en Redis.
    """

    # Se encarga de interpretar los argumentos que le pasamos al script desde la consola.
    parser = argparse.ArgumentParser(description="Seed Redis con datos de BeMyGuest")
    parser.add_argument("--reset",   action="store_true", help="Elimina keys previas antes de cargar")
    parser.add_argument("--dry-run", action="store_true", help="Muestra las keys sin escribirlas")
    parser.add_argument("--fallback", action="store_true", help="Usa dataset ficticio aunque Mongo esté disponible")
    args = parser.parse_args()

    #Validar conexion
    try:
        r = get_redis()
        print(f"Redis conectado en {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        print(f"(ERROR) No se pudo conectar a Redis: {e}")
        sys.exit(1)

    # Reset opcional de Redis antes de cargar la data.
    if args.reset and not args.dry_run:
        reset_redis(r)

    # Fuente de habitaciones (datos)
    habitaciones = []

    if not args.fallback:
        try:
            db = get_mongo()
            habitaciones = list(db["habitaciones"].find({}, {"_id": 1, "disponible": 1, "numero": 1, "tipo": 1}))
            print(f"MongoDB conectado. {len(habitaciones)} habitaciones encontradas.")
        except Exception as e:
            print(f"MongoDB no disponible ({e}). Usando dataset de fallback.")

    if not habitaciones:
        habitaciones = FALLBACK_HABITACIONES
        print(f"Usando {len(habitaciones)} habitaciones del dataset de fallback.")

    # seed
    entradas = construir_entradas(habitaciones)
    seed(r, entradas, dry_run=args.dry_run)

    if not args.dry_run:
        #resumencito de lo que sucedió
        print("\n-- Estado en Redis --")
        disp = sum(1 for h in habitaciones if h.get("disponible", True))
        no_disp = len(habitaciones) - disp
        print(f"  Habitaciones disponibles   : {disp}")
        print(f"  Habitaciones no disponibles: {no_disp}")
        print(f"  Total keys de disponibilidad: {len(entradas)}")
        print(f"  stats:reservas:hoy          : {r.get('stats:reservas:hoy')}")


if __name__ == "__main__":
    main()
