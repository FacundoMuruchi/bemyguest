import json
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

try:
    from .config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
except ImportError:
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD



def get_driver():
    #Devuelve un driver de Neo4j o lanza serviceunaavailable
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def ping():
    # verifica conexion 
    try:
        driver = get_driver()
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False



def crear_constraints(driver):
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:Usuario) REQUIRE u.id IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (h:Hotel) REQUIRE h.id IS UNIQUE"
        )




def crear_usuario(driver, usuario_id: str, nombre: str, apellido: str):
    #merge para evitar duplicados
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



def crear_relacion_reserva(driver,usuario_id: str,hotel_id: str,fecha_reserva: str,noches: int,estado: str,):
  
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


def crear_relacion_calificacion(driver,usuario_id: str,hotel_id: str,puntaje: float,fecha: str,):
    
    with driver.session() as session:
        session.run(
            """
            MATCH (u:Usuario {id: $usuario_id})
            MATCH (h:Hotel   {id: $hotel_id})
            MERGE (u)-[r:CALIFICO {fecha: $fecha}]->(h)
            SET r.puntaje = $puntaje
            """,
            usuario_id=usuario_id,
            hotel_id=hotel_id,
            puntaje=puntaje,
            fecha=fecha,
        )





def importar_dataset(path, reset=True):
    
    dataset_path = Path(path)
    with dataset_path.open("r", encoding="utf-8") as f:
        dataset = json.load(f)

    driver = get_driver()

    if reset:
        limpiar_grafo(driver)

    crear_constraints(driver)

    # Nodos Usuario
    usuarios = dataset.get("usuarios", [])
    for u in usuarios:
        crear_usuario(driver, u["_id"], u.get("nombre", ""), u.get("apellido", ""))

    # Nodos Hotel
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

    # Relaciones RESERVO (reservas → hotel_id, usuario_id)
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

    # Relaciones CALIFICO (reseñas → calificacion.general)
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
        "usuarios":  len(usuarios),
        "hoteles":   len(hoteles),
        "reservas":  len(reservas),
        "resenas":   len(resenas),
    }


# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------

def limpiar_grafo(driver):
    #Elimina todos los nodos y relaciones del grafo
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

