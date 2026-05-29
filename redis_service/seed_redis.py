"""
seed_redis.py — BeMyGuest
=========================
Pobla Redis con el estado de disponibilidad de las habitaciones
leyendo los documentos reales de MongoDB.

Uso:
    uv run redis_service/seed_redis.py
    uv run redis_service/seed_redis.py --reset      # limpia Redis antes de cargar
    uv run redis_service/seed_redis.py --dry-run    # muestra las keys sin escribir
"""

import argparse
import os
import sys

import redis
from pymongo import MongoClient

# ── Conexión ──────────────────────────────────────────────────────────────────

MONGO_URI   = os.getenv("MONGO_URI",   "mongodb://localhost:27017")
REDIS_HOST  = os.getenv("REDIS_HOST",  "localhost")
REDIS_PORT  = int(os.getenv("REDIS_PORT", 6379))
DB_NAME     = "bemyguest"


def get_mongo():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")           # falla rápido si no hay conexión
    return client[DB_NAME]


def get_redis():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    return r


# ── Dataset de fallback (sin Mongo) ──────────────────────────────────────────
# IDs ficticios con formato ObjectId (24 hex). Útiles para pruebas unitarias
# cuando MongoDB no está disponible.

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


# ── Lógica de seeding ─────────────────────────────────────────────────────────

def build_entries(habitaciones: list) -> list[tuple[str, str]]:
    """Devuelve lista de (key, value) para disponibilidad."""
    entries = []
    for h in habitaciones:
        hab_id = str(h["_id"])
        value  = "1" if h.get("disponible", True) else "0"
        entries.append((f"habitacion:{hab_id}:disponible", value))
    return entries


def seed(r: redis.Redis, entries: list[tuple[str, str]], dry_run: bool):
    if dry_run:
        print("\n[DRY-RUN] Keys que se escribirían en Redis:")
        for key, val in entries:
            estado = "disponible" if val == "1" else "no disponible"
            print(f"  SET {key!r:60s} → {val}  ({estado})")
        print(f"\nTotal: {len(entries)} keys")
        return

    pipe = r.pipeline()
    for key, val in entries:
        pipe.set(key, val)

    # Inicializar contador de reservas de hoy si no existe
    pipe.setnx("stats:reservas:hoy", "0")
    pipe.expire("stats:reservas:hoy", 86400)

    pipe.execute()
    print(f"✅  {len(entries)} keys de disponibilidad cargadas en Redis.")
    print(f"✅  stats:reservas:hoy inicializado.")


def reset_redis(r: redis.Redis):
    """Elimina TODAS las keys del dataset BeMyGuest (no hace FLUSHALL)."""
    patterns = [
        "habitacion:*:disponible",
        "lock:habitacion:*",
        "sesion:*",
        "stats:reservas:*",
    ]
    deleted = 0
    for pattern in patterns:
        keys = r.keys(pattern)
        if keys:
            deleted += r.delete(*keys)
    print(f"🗑️   {deleted} keys eliminadas de Redis.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed Redis con datos de BeMyGuest")
    parser.add_argument("--reset",   action="store_true", help="Elimina keys previas antes de cargar")
    parser.add_argument("--dry-run", action="store_true", help="Muestra las keys sin escribirlas")
    parser.add_argument("--fallback", action="store_true", help="Usa dataset ficticio aunque Mongo esté disponible")
    args = parser.parse_args()

    # ── Redis ──────────────────────────────────────────────────────────────────
    try:
        r = get_redis()
        print(f"✅  Redis conectado en {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        print(f"❌  No se pudo conectar a Redis: {e}")
        sys.exit(1)

    # ── Opcional: reset previo ─────────────────────────────────────────────────
    if args.reset and not args.dry_run:
        reset_redis(r)

    # ── Fuente de datos ────────────────────────────────────────────────────────
    habitaciones = []

    if not args.fallback:
        try:
            db = get_mongo()
            habitaciones = list(db["habitaciones"].find({}, {"_id": 1, "disponible": 1, "numero": 1, "tipo": 1}))
            print(f"✅  MongoDB conectado. {len(habitaciones)} habitaciones encontradas.")
        except Exception as e:
            print(f"⚠️   MongoDB no disponible ({e}). Usando dataset de fallback.")

    if not habitaciones:
        habitaciones = FALLBACK_HABITACIONES
        print(f"ℹ️   Usando {len(habitaciones)} habitaciones del dataset de fallback.")

    # ── Seed ──────────────────────────────────────────────────────────────────
    entries = build_entries(habitaciones)
    seed(r, entries, dry_run=args.dry_run)

    if not args.dry_run:
        # ── Resumen post-seed ──────────────────────────────────────────────────
        print("\n── Estado en Redis (post-seed) ──────────────────────────────────────")
        disp = sum(1 for h in habitaciones if h.get("disponible", True))
        no_disp = len(habitaciones) - disp
        print(f"  Habitaciones disponibles   : {disp}")
        print(f"  Habitaciones no disponibles: {no_disp}")
        print(f"  Total keys de disponibilidad: {len(entries)}")
        print(f"  stats:reservas:hoy          : {r.get('stats:reservas:hoy')}")


if __name__ == "__main__":
    main()
