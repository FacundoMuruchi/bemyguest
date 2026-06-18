import json
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

try:
    from .config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
except ImportError:
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def get_driver():
    # Devuelve un driver para conectarse a Neo4j
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def ping():
    # Verifica si Neo4j está disponible, devuelve True o False
    try:
        driver = get_driver()
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

def crear_constraints(driver):
    # Asegura que no haya dos usuarios o hoteles con el mismo id
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:Usuario) REQUIRE u.id IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (h:Hotel) REQUIRE h.id IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (hab:Habitacion) REQUIRE hab.id IS UNIQUE"
        )

# ---------------------------------------------------------------------------
# Creación de nodos
# ---------------------------------------------------------------------------

def crear_usuario(driver, usuario_id: str, nombre: str, apellido: str):
    # Crea un nodo Usuario, si ya existe lo actualiza (MERGE evita duplicados)
    with driver.session() as session:
        session.run(
            """
            MERGE (u:Usuario {id: $id})
            SET u.nombre   = $nombre,
                u.apellido = $apellido
            """,
            id=usuario_id,
            nombre=nombre,
            apellido=apellido,
        )


def crear_hotel(driver, hotel_id: str, nombre: str, ciudad: str, pais: str, categoria: int):
    # Crea un nodo Hotel, si ya existe lo actualiza
    with driver.session() as session:
        session.run(
            """
            MERGE (h:Hotel {id: $id})
            SET h.nombre    = $nombre,
                h.ciudad    = $ciudad,
                h.pais      = $pais,
                h.categoria = $categoria
            """,
            id=hotel_id,
            nombre=nombre,
            ciudad=ciudad,
            pais=pais,
            categoria=categoria,
        )

def crear_habitacion(driver, habitacion_id: str, numero: str, tipo: str, precio: float, disponible: bool):
    # Solo crea el nodo Habitacion
    with driver.session() as session:
        session.run(
            """
            MERGE (hab:Habitacion {id: $id})
            SET hab.numero     = $numero,
                hab.tipo       = $tipo,
                hab.precio     = $precio,
                hab.disponible = $disponible
            """,
            id=habitacion_id,
            numero=numero,
            tipo=tipo,
            precio=precio,
            disponible=disponible,
        )


# ---------------------------------------------------------------------------
# Creación de relaciones
# ---------------------------------------------------------------------------

def crear_relacion_reserva(driver, usuario_id: str, hotel_id: str, fecha_reserva: str, noches: int, estado: str):
    # Conecta un Usuario con un Hotel mediante la relación RESERVO
    with driver.session() as session:
        session.run(
            """
            MATCH (u:Usuario {id: $usuario_id})
            MATCH (h:Hotel   {id: $hotel_id})
            MERGE (u)-[r:RESERVO {fecha_reserva: $fecha_reserva}]->(h)
            SET r.noches = $noches,
                r.estado = $estado
            """,
            usuario_id=usuario_id,
            hotel_id=hotel_id,
            fecha_reserva=fecha_reserva,
            noches=noches,
            estado=estado,
        )


def crear_relacion_calificacion(driver, usuario_id: str, hotel_id: str, puntaje: float, fecha: str):
    # Conecta un Usuario con un Hotel mediante la relación CALIFICO
    with driver.session() as session:
        session.run(
           """
            MATCH (u:Usuario {id: $usuario_id})
            MATCH (h:Hotel   {id: $hotel_id})

            CREATE (u)-[r:CALIFICO {
                fecha: $fecha,
                puntaje: $puntaje
            }]->(h)
            """,
            usuario_id=usuario_id,
            hotel_id=hotel_id,
            puntaje=puntaje,
            fecha=fecha,
        )

def crear_relacion_habitacion_hotel(driver, habitacion_id: str, hotel_id: str):
    # Conecta un Hotel con una Habitacion mediante la relación TIENE
    with driver.session() as session:
        session.run(
            """
            MATCH (h:Hotel {id: $hotel_id})
            MATCH (hab:Habitacion {id: $hab_id})
            MERGE (h)-[:TIENE]->(hab)
            """,
            hotel_id=hotel_id,
            hab_id=habitacion_id,
        )


# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------

def limpiar_grafo(driver):
    # Borra todos los nodos y relaciones del grafo
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


# ---------------------------------------------------------------------------
# Importación del dataset
# ---------------------------------------------------------------------------

def importar_dataset(path, reset=True):
    # Lee el archivo JSON y carga usuarios, hoteles, reservas y reseñas en el grafo
    # Si reset=True borra todo primero para evitar duplicados
    dataset_path = Path(path)
    with dataset_path.open("r", encoding="utf-8") as f:
        dataset = json.load(f)

    driver = get_driver()

    if reset:
        limpiar_grafo(driver)

    crear_constraints(driver)

    usuarios = dataset.get("usuarios", [])
    for u in usuarios:
        crear_usuario(driver, u["_id"], u.get("nombre", ""), u.get("apellido", ""))

    hoteles = dataset.get("hoteles", [])
    for h in hoteles:
        crear_hotel(
            driver,
            h["_id"],
            h.get("nombre", ""),
            h.get("ciudad", ""),
            h.get("pais", ""),
            h.get("categoria", 0),
        )

    habitaciones = dataset.get("habitaciones", [])
    for hab in habitaciones:
        crear_habitacion(
            driver,
            hab["_id"],
            hab.get("numero", ""),
            hab.get("tipo", ""),
            hab.get("precio_por_noche", 0.0),
            hab.get("disponible", True),
        )
        crear_relacion_habitacion_hotel(driver, hab["_id"], hab["hotel_id"])
        

    reservas = dataset.get("reservas", [])
    for r in reservas:
        crear_relacion_reserva(
            driver,
            r["usuario_id"],
            r["hotel_id"],
            r.get("fecha_reserva", ""),
            r.get("noches", 0),
            r.get("estado", ""),
        )

    resenas = dataset.get("resenas", [])
    for res in resenas:
        puntaje = res.get("calificacion", {}).get("general", 0.0)
        crear_relacion_calificacion(
            driver,
            res["usuario_id"],
            res["hotel_id"],
            puntaje,
            res.get("fecha", ""),
        )
    
    

    driver.close()

    return {
        "usuarios": len(usuarios),
        "hoteles":  len(hoteles),
        "reservas": len(reservas),
        "resenas":  len(resenas),
        "habitaciones":len(habitaciones),
    }


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
    
def estadisticas_grafo(driver) -> dict:
    # Devuelve cuántos nodos y relaciones hay en el grafo
    with driver.session() as session:
        r = session.run(
            """
            MATCH (u:Usuario) WITH count(u) AS usuarios
            MATCH (h:Hotel) WITH usuarios, count(h) AS hoteles
            MATCH (hab:Habitacion) WITH usuarios, hoteles, count(hab) AS habitaciones
            OPTIONAL MATCH ()-[res:RESERVO]->() WITH usuarios, hoteles, habitaciones, count(res) AS reservas
            OPTIONAL MATCH ()-[cal:CALIFICO]->() WITH usuarios, hoteles, habitaciones, reservas, count(cal) AS calificaciones
            OPTIONAL MATCH ()-[t:TIENE]->() RETURN usuarios, hoteles, habitaciones, reservas, calificaciones, count(t) AS relaciones_tiene
            """
        )
        row = r.single()
        if row:
            return dict(row)
        return {
            "usuarios": 0,
            "hoteles": 0,
            "habitaciones": 0,
            "reservas": 0,
            "calificaciones": 0,
            "habitaciones asignadas": 0,
        }


def recomendar_por_reservas(driver, usuario_id: str, limite: int = 5) -> list:
    # Filtrado colaborativo: recomienda hoteles que reservaron usuarios con historial similar
    with driver.session() as session:
        result = session.run(
            """
            MATCH (yo:Usuario {id: $usuario_id})-[:RESERVO]->(h:Hotel)
                  <-[:RESERVO]-(similar:Usuario)-[:RESERVO]->(recomendado:Hotel)
            WHERE yo <> similar
              AND NOT (yo)-[:RESERVO]->(recomendado)
            RETURN recomendado.id        AS hotel_id,
                   recomendado.nombre   AS nombre,
                   recomendado.ciudad   AS ciudad,
                   recomendado.pais     AS pais,
                   recomendado.categoria AS categoria,
                   count(similar)       AS coincidencias
            ORDER BY coincidencias DESC
            LIMIT $limite
            """,
            usuario_id=usuario_id,
            limite=limite,
        )
        return [dict(r) for r in result]


def recomendar_por_calificaciones(driver, usuario_id: str, limite: int = 5) -> list:
    # Filtrado colaborativo: recomienda hoteles bien calificados por usuarios con gustos similares
    with driver.session() as session:
        result = session.run(
            """
            MATCH (yo:Usuario {id: $usuario_id})-[c1:CALIFICO]->(h:Hotel)
                  <-[c2:CALIFICO]-(similar:Usuario)-[c3:CALIFICO]->(recomendado:Hotel)
            WHERE yo <> similar
              AND c1.puntaje >= 3.5
              AND c2.puntaje >= 3.5
              AND c3.puntaje >= 3.5
              AND NOT (yo)-[:CALIFICO]->(recomendado)
              AND NOT (yo)-[:RESERVO]->(recomendado)
            RETURN recomendado.id         AS hotel_id,
                   recomendado.nombre    AS nombre,
                   recomendado.ciudad    AS ciudad,
                   recomendado.pais      AS pais,
                   recomendado.categoria AS categoria,
                   count(similar)        AS coincidencias,
                   round(avg(c3.puntaje) * 10) / 10 AS puntaje_promedio
            ORDER BY coincidencias DESC
            LIMIT $limite
            """,
            usuario_id=usuario_id,
            limite=limite,
        )
        return [dict(r) for r in result]


def hoteles_mas_populares(driver, limite: int = 10) -> list:
    # Devuelve los hoteles con más reservas en toda la plataforma
    with driver.session() as session:
        result = session.run(
            """
            MATCH (u:Usuario)-[:RESERVO]->(h:Hotel)
            RETURN h.id         AS hotel_id,
                   h.nombre    AS nombre,
                   h.ciudad    AS ciudad,
                   h.pais      AS pais,
                   h.categoria AS categoria,
                   count(u)    AS total_reservas
            ORDER BY total_reservas DESC
            LIMIT $limite
            """,
            limite=limite,
        )
        return [dict(r) for r in result]


def usuarios_similares(driver, usuario_id: str, limite: int = 5) -> list:
    # Devuelve usuarios que tienen más hoteles reservados en común con el usuario dado
    with driver.session() as session:
        result = session.run(
            """
            MATCH (yo:Usuario {id: $usuario_id})-[:RESERVO]->(h:Hotel)
                  <-[:RESERVO]-(similar:Usuario)
            WHERE yo <> similar
            RETURN similar.id        AS usuario_id,
                   similar.nombre   AS nombre,
                   similar.apellido AS apellido,
                   count(h)          AS hoteles_en_comun
            ORDER BY hoteles_en_comun DESC
            LIMIT $limite
            """,
            usuario_id=usuario_id,
            limite=limite,
        )
        return [dict(r) for r in result]
