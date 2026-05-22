import argparse
import json
import random
from datetime import timedelta
from pathlib import Path

from faker import Faker


DEFAULT_COUNTS = {
    "usuarios": 300,
    "hoteles": 60,
    "habitaciones": 300,
    "reservas": 600,
    "resenas": 240,
}

SERVICE_OPTIONS = ["wifi", "pileta", "spa", "estacionamiento", "gimnasio", "restaurante"]
EXTRA_SERVICE_OPTIONS = ["desayuno", "media_pension", "pension_completa", "transfer", "city_tour"]
ROOM_TYPES = {
    "estandar": {"cama": "doble", "metros": (18, 25), "precio": (6000, 12000)},
    "superior": {"cama": "queen", "metros": (25, 35), "precio": (12000, 20000)},
    "suite": {"cama": "king size", "metros": (40, 70), "precio": (20000, 40000)},
    "cabaña": {"cama": "doble", "metros": (30, 50), "precio": (15000, 30000)},
}
ROOM_VIEWS = ["jardín", "calle", "montaña", "lago", "mar"]
BOOKING_STATES = ["confirmada", "pendiente", "cancelada"]


def build_id(prefix, number):
    return f"{prefix}{number:04d}"


def generate_usuarios(fake, count):
    usuarios = []
    used_emails = set()

    for number in range(1, count + 1):
        email = fake.unique.email()
        while email in used_emails:
            email = fake.unique.email()
        used_emails.add(email)

        usuarios.append(
            {
                "_id": build_id("USR", number),
                "nombre": fake.first_name(),
                "apellido": fake.last_name(),
                "email": email,
                "telefono": fake.phone_number(),
                "pais": fake.country(),
                "ciudad": fake.city(),
            }
        )

    return usuarios


def generate_hoteles(fake, count):
    hoteles = []

    for number in range(1, count + 1):
        hoteles.append(
            {
                "_id": build_id("HOT", number),
                "nombre": f"Hotel {fake.last_name()}",
                "ciudad": fake.city(),
                "pais": fake.country(),
                "categoria": random.randint(1, 5),
                "servicios": random.sample(SERVICE_OPTIONS, k=random.randint(2, 4)),
                "calificacion_promedio": round(random.uniform(3.0, 5.0), 1),
            }
        )

    return hoteles


def generate_habitaciones(count, hoteles):
    habitaciones = []
    hotel_ids = [hotel["_id"] for hotel in hoteles]

    for number in range(1, count + 1):
        hotel_id = hotel_ids[(number - 1) % len(hotel_ids)]
        room_index = ((number - 1) // len(hotel_ids)) + 1
        floor = random.randint(1, 8)
        tipo = list(ROOM_TYPES.keys())[(number - 1) % len(ROOM_TYPES)]
        specs = ROOM_TYPES[tipo]

        habitaciones.append(
            {
                "_id": build_id("HAB", number),
                "hotel_id": hotel_id,
                "numero": f"{floor}{room_index:02d}",
                "tipo": tipo,
                "capacidad_adultos": random.randint(1, 6),
                "precio_por_noche": round(random.uniform(*specs["precio"]), 2),
                "disponible": random.choice([True, False]),
                "amenities": {
                    "cama": specs["cama"],
                    "metros_cuadrados": random.randint(*specs["metros"]),
                    "vista": ROOM_VIEWS[(number - 1) % len(ROOM_VIEWS)],
                    "tv_smart": True,
                    "aire_acondicionado": random.choice([True, False]),
                    "jacuzzi": tipo in ("suite", "cabaña") and random.choice([True, False]),
                    "terraza": tipo == "cabaña",
                },
            }
        )

    return habitaciones


def generate_reservas(fake, count, usuarios, habitaciones):
    reservas = []

    for number in range(1, count + 1):
        usuario = random.choice(usuarios)
        habitacion = random.choice(habitaciones)
        check_in = fake.date_between(start_date="-6m", end_date="+6m")
        noches = random.randint(1, 14)
        fecha_reserva = check_in - timedelta(days=random.randint(0, 90))

        reservas.append(
            {
                "_id": build_id("RSV", number),
                "usuario_id": usuario["_id"],
                "habitacion_id": habitacion["_id"],
                "hotel_id": habitacion["hotel_id"],
                "check_in": check_in.isoformat(),
                "check_out": (check_in + timedelta(days=noches)).isoformat(),
                "noches": noches,
                "huespedes": random.randint(1, habitacion["capacidad_adultos"]),
                "estado": random.choice(BOOKING_STATES),
                "servicios_extra": random.sample(EXTRA_SERVICE_OPTIONS, k=random.randint(0, 2)),
                "fecha_reserva": fecha_reserva.isoformat(),
            }
        )

    return reservas


def generate_resenas(fake, count, usuarios, hoteles):
    resenas = []

    for number in range(1, count + 1):
        usuario = random.choice(usuarios)
        hotel = random.choice(hoteles)

        resenas.append(
            {
                "_id": build_id("RES", number),
                "hotel_id": hotel["_id"],
                "usuario_id": usuario["_id"],
                "calificacion": {
                    "general": round(random.uniform(2.5, 5.0), 1),
                    "limpieza": random.randint(1, 5),
                    "atencion": random.randint(1, 5),
                    "ubicacion": random.randint(1, 5),
                },
                "comentario": fake.paragraph(nb_sentences=2),
                "fecha": fake.date_between(start_date="-1y", end_date="today").isoformat(),
            }
        )

    return resenas


def generate_dataset(seed):
    random.seed(seed)
    fake = Faker("es_AR")
    Faker.seed(seed)

    hoteles = generate_hoteles(fake, DEFAULT_COUNTS["hoteles"])
    habitaciones = generate_habitaciones(DEFAULT_COUNTS["habitaciones"], hoteles)
    usuarios = generate_usuarios(fake, DEFAULT_COUNTS["usuarios"])
    reservas = generate_reservas(fake, DEFAULT_COUNTS["reservas"], usuarios, habitaciones)
    resenas = generate_resenas(fake, DEFAULT_COUNTS["resenas"], usuarios, hoteles)

    return {
        "metadata": {
            "name": "bemyguest_mock_dataset",
            "version": "1.0",
            "total_records": sum(DEFAULT_COUNTS.values()),
            "counts": DEFAULT_COUNTS,
            "seed": seed,
        },
        "usuarios": usuarios,
        "hoteles": hoteles,
        "habitaciones": habitaciones,
        "reservas": reservas,
        "resenas": resenas,
    }


def validate_unique_ids(dataset, collection_name):
    ids = [doc["_id"] for doc in dataset[collection_name]]
    if len(ids) != len(set(ids)):
        raise ValueError(f"IDs duplicados en {collection_name}")


def validate_dataset(dataset):
    counts = {name: len(dataset[name]) for name in DEFAULT_COUNTS}
    total_records = sum(counts.values())
    if counts != DEFAULT_COUNTS:
        raise ValueError(f"Distribucion invalida: {counts}")
    if dataset["metadata"]["total_records"] != total_records:
        raise ValueError("metadata.total_records no coincide con la suma de entidades")

    for collection_name in DEFAULT_COUNTS:
        validate_unique_ids(dataset, collection_name)

    hotel_ids = {hotel["_id"] for hotel in dataset["hoteles"]}
    usuario_ids = {usuario["_id"] for usuario in dataset["usuarios"]}
    habitaciones_by_id = {habitacion["_id"]: habitacion for habitacion in dataset["habitaciones"]}

    for habitacion in dataset["habitaciones"]:
        if habitacion["hotel_id"] not in hotel_ids:
            raise ValueError(f"Habitacion con hotel_id inexistente: {habitacion['_id']}")

    for reserva in dataset["reservas"]:
        habitacion = habitaciones_by_id.get(reserva["habitacion_id"])
        if reserva["usuario_id"] not in usuario_ids:
            raise ValueError(f"Reserva con usuario_id inexistente: {reserva['_id']}")
        if habitacion is None:
            raise ValueError(f"Reserva con habitacion_id inexistente: {reserva['_id']}")
        if reserva["hotel_id"] != habitacion["hotel_id"]:
            raise ValueError(f"Reserva con hotel_id inconsistente: {reserva['_id']}")
        if reserva["check_out"] <= reserva["check_in"]:
            raise ValueError(f"Reserva con fechas invalidas: {reserva['_id']}")
        if reserva["fecha_reserva"] > reserva["check_in"]:
            raise ValueError(f"Reserva con fecha_reserva invalida: {reserva['_id']}")

    for resena in dataset["resenas"]:
        if resena["usuario_id"] not in usuario_ids:
            raise ValueError(f"Resena con usuario_id inexistente: {resena['_id']}")
        if resena["hotel_id"] not in hotel_ids:
            raise ValueError(f"Resena con hotel_id inexistente: {resena['_id']}")

    return counts


def write_dataset(dataset, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(dataset, file, ensure_ascii=False, indent=2)
        file.write("\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Genera el dataset mock unico de BeMyGuest.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("mock_data") / "bemyguest_dataset.json",
        help="Ruta del archivo JSON a generar.",
    )
    parser.add_argument("--seed", type=int, default=20260522, help="Seed para generar datos reproducibles.")
    return parser.parse_args()


def main():
    args = parse_args()
    dataset = generate_dataset(args.seed)
    counts = validate_dataset(dataset)
    write_dataset(dataset, args.output)
    print(f"Dataset generado en {args.output}")
    print(f"Total registros: {sum(counts.values())}")
    for collection_name, count in counts.items():
        print(f"- {collection_name}: {count}")


if __name__ == "__main__":
    main()
