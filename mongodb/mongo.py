import faker
import random
from datetime import timedelta

try:
    from .config import *
except:
    from config import *

fake = faker.Faker()

# ── FUNCIONES MONGO ──────────────────────────────────────────────────────────────────
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
    collection.insert_one(documento)

def eliminar_documento(collection, criterio):
    collection.delete_one(criterio)

def eliminar_todos_documentos(collection):
    collection.delete_many({})

# ── USUARIOS ──────────────────────────────────────────────────────────────────
def insertar_usuarios_faker(n):
    for _ in range(n):
        usuario = {
            "nombre":     fake.first_name(),
            "apellido":   fake.last_name(),
            "email":      fake.email(),
            "telefono":   fake.phone_number(),
            "pais":         fake.country(),
            "ciudad":       fake.city()
        }
        insertar_documento(col_usuarios, usuario)
    print(f"{n} usuarios insertados.")

# ── HOTELES ──────────────────────────────────────────────────────────────────
def insertar_hoteles_faker(n):
    for _ in range(n):
        hotel = {
            "nombre":    "Hotel " + fake.last_name(),
            "ciudad":   fake.city(),
            "pais":      fake.country(),
            "categoria": random.randint(1, 5),
            "servicios": random.sample(
                ["wifi", "pileta", "spa", "estacionamiento", "gimnasio", "restaurante"],
                k=random.randint(2, 4)
            ),
            "calificacion_promedio": round(random.uniform(3.0, 5.0), 1)
            }
        insertar_documento(col_hoteles, hotel)
    print(f"{n} hoteles insertados.")


# ── HABITACIONES ─────────────────────────────────────────────────────────────
TIPOS = {
    "estandar":  {"cama": "doble",     "metros": (18, 25), "precio": (6000,  120)},
    "superior":  {"cama": "queen",     "metros": (25, 35), "precio": (12000, 20000)},
    "suite":     {"cama": "king size", "metros": (40, 70), "precio": (20000, 40000)},
    "cabaña":    {"cama": "doble",     "metros": (30, 50), "precio": (15000, 30000)},
}

def insertar_habitaciones_faker(hotel_ids, hab_por_hotel=5):
    for hotel_id in hotel_ids:
        for numero in range(1, hab_por_hotel + 1):
            tipo  = random.choice(list(TIPOS.keys()))
            specs = TIPOS[tipo]
            habitacion = {
                "hotel_id":          hotel_id,
                "numero":            str(random.randint(1, 4)) + f"{numero:02d}",
                "tipo":              tipo,
                "capacidad":         random.randint(1, 6),
                "precio_por_noche":  round(random.uniform(*specs["precio"]), 2),
                "disponible":        random.choice([True, False]),
                "amenities": {
                    "cama":              specs["cama"],
                    "metros_cuadrados":  random.randint(*specs["metros"]),
                    "vista":             random.choice(["jardín", "calle", "montaña", "lago", "mar"]),
                    "tv_smart":          True,
                    **({"aire_acondicionado": True} if random.choice([True, False]) else {}),
                    **({"jacuzzi": True} if tipo in ("suite", "cabaña") else {}),
                    **({"terraza": True} if tipo == "cabaña" else {}),
                }
            }
            insertar_documento(col_habitaciones, habitacion)
    print(f"{hab_por_hotel} habitaciones insertadas para {len(hotel_ids)} hoteles.")


# ── RESERVAS ─────────────────────────────────────────────────────────────────
ESTADOS = ["confirmada", "pendiente", "cancelada"]

def insertar_reservas_faker(n):
    # tomamos IDs reales de habitaciones disponibles
    habitaciones = list(col_habitaciones.find({"disponible": True}, {"_id": 1, "hotel_id": 1}))
    if not habitaciones:
        print("No hay habitaciones disponibles. Insertá habitaciones primero.")
        return

    for _ in range(n):
        hab      = random.choice(habitaciones)
        usr = random.choice(list(col_usuarios.find({}, {"_id": 1})))
        check_in = fake.date_between(start_date="-6m", end_date="+3m")
        noches   = random.randint(1, 10)
        reserva  = {
            "usuario_id":    usr["_id"],
            "habitacion_id": hab["_id"],
            "hotel_id":      hab["hotel_id"],
            "check_in":      check_in.isoformat(),
            "check_out":     (check_in + timedelta(days=noches)).isoformat(),
            "noches":        noches,
            "huespedes":     random.randint(1, 3),
            "estado":        random.choice(ESTADOS),
            "servicios_extra": random.sample(
                ["desayuno", "media_pension", "pension_completa", "transfer", "city_tour"],
                k=random.randint(0, 2)
            ),
            "fecha_reserva": fake.date_time_this_year().isoformat()
        }
        insertar_documento(col_reservas, reserva)
    print(f"{n} reservas insertadas.")


# ── RESEÑAS ──────────────────────────────────────────────────────────────────
def insertar_resenas_faker(n):
    hoteles = list(col_hoteles.find({}, {"_id": 1}))
    if not hoteles:
        print("No hay hoteles. Insertá hoteles primero.")
        return

    for _ in range(n):
        hotel = random.choice(hoteles)
        usr = random.choice(list(col_usuarios.find({}, {"_id": 1})))
        resena = {
            "hotel_id":   hotel["_id"],
            "usuario_id": usr["_id"],
            "calificacion": {
                "general":    round(random.uniform(2.5, 5.0), 1),
                "limpieza":   random.randint(1, 5),
                "atencion":   random.randint(1, 5),
                "ubicacion":  random.randint(1, 5),
            },
            "comentario": fake.paragraph(nb_sentences=2),
            "fecha":      fake.date_time_this_year().isoformat()
        }
        insertar_documento(col_reseñas, resena)
    print(f"{n} reseñas insertadas.")
