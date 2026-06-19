from pathlib import Path

import pandas as pd
import streamlit as st

from implementacion_neo4j import neo4j_service


DEFAULT_DATASET_PATH = Path("mock_data") / "bemyguest_dataset.json"


def get_driver():
    return neo4j_service.get_driver()


def run_query(query, **params):
    driver = get_driver()
    try:
        with driver.session() as session:
            return [dict(row) for row in session.run(query, **params)]
    finally:
        driver.close()


def load_usuarios():
    return run_query(
        """
        MATCH (u:Usuario)
        RETURN u.id AS id, u.nombre AS nombre, u.apellido AS apellido
        ORDER BY u.id
        LIMIT 500
        """
    )


def usuario_label(usuario):
    return f"{usuario.get('nombre', '')} {usuario.get('apellido', '')} | {usuario.get('id')}"


def show_dataframe(rows):
    if not rows:
        st.info("No se encontraron resultados.")
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with st.expander("JSON"):
        st.json(rows)


def show_dashboard():
    driver = get_driver()
    try:
        stats = neo4j_service.estadisticas_grafo(driver)
    finally:
        driver.close()

    columns = st.columns(len(stats))
    for column, (name, value) in zip(columns, stats.items()):
        column.metric(name.replace("_", " ").capitalize(), value)


def show_recommendations_tab():
    st.subheader("Recomendaciones")
    usuarios = load_usuarios()
    if not usuarios:
        st.info("No hay usuarios cargados en el grafo.")
        return

    usuario = st.selectbox("Usuario", usuarios, format_func=usuario_label)
    usuario_id = usuario["id"]

    tab_reservas, tab_calificaciones, tab_populares, tab_similares = st.tabs(
        ["Por reservas", "Por calificaciones", "Hoteles populares", "Usuarios similares"]
    )

    driver = get_driver()
    try:
        with tab_reservas:
            st.caption("Usuarios que reservaron lo mismo que vos también reservaron estos otros hoteles.")
            show_dataframe(neo4j_service.recomendar_por_reservas(driver, usuario_id))
        with tab_calificaciones:
            st.caption("Hoteles recomendados por usuarios con reseñas similares a las tuyas.")
            show_dataframe(neo4j_service.recomendar_por_calificaciones(driver, usuario_id))
        with tab_populares:
            limite = st.slider("Cantidad", min_value=5, max_value=20, value=10)
            show_dataframe(neo4j_service.hoteles_mas_populares(driver, limite))
        with tab_similares:
            show_dataframe(neo4j_service.usuarios_similares(driver, usuario_id))
    finally:
        driver.close()


def show_graph_explorer_tab():
    st.subheader("Explorar grafo")
    query_name = st.selectbox(
        "Consulta",
        [
            "Hoteles con habitaciones",
            "Reservas por usuario",
            "Calificaciones por hotel",
            "Habitaciones por hotel",
        ],
    )
    limit = st.slider("Cantidad máxima", min_value=5, max_value=100, value=20, step=5)

    if query_name == "Hoteles con habitaciones":
        rows = run_query(
            """
            MATCH (h:Hotel)-[:TIENE]->(hab:Habitacion)
            RETURN h.id AS hotel_id, h.nombre AS hotel, hab.id AS habitacion_id,
                   hab.numero AS numero, hab.tipo AS tipo
            ORDER BY h.nombre, hab.numero
            LIMIT $limit
            """,
            limit=limit,
        )
    elif query_name == "Reservas por usuario":
        rows = run_query(
            """
            MATCH (u:Usuario)-[r:RESERVO]->(h:Hotel)
            RETURN u.id AS usuario_id, u.nombre AS nombre, u.apellido AS apellido,
                   h.id AS hotel_id, h.nombre AS hotel, r.fecha_reserva AS fecha_reserva,
                   r.noches AS noches, r.estado AS estado
            ORDER BY r.fecha_reserva DESC
            LIMIT $limit
            """,
            limit=limit,
        )
    elif query_name == "Calificaciones por hotel":
        rows = run_query(
            """
            MATCH (u:Usuario)-[r:CALIFICO]->(h:Hotel)
            RETURN h.id AS hotel_id, h.nombre AS hotel, u.id AS usuario_id,
                   u.nombre AS nombre, r.fecha AS fecha, r.puntaje AS puntaje
            ORDER BY r.fecha DESC
            LIMIT $limit
            """,
            limit=limit,
        )
    else:
        rows = run_query(
            """
            MATCH (h:Hotel)-[:TIENE]->(hab:Habitacion)
            RETURN h.id AS hotel_id, h.nombre AS hotel, count(hab) AS habitaciones
            ORDER BY habitaciones DESC
            LIMIT $limit
            """,
            limit=limit,
        )

    show_dataframe(rows)


def main():
    st.set_page_config(page_title="BeMyGuest - Neo4j", layout="wide", page_icon="🕸️")
    st.title("BeMyGuest Neo4j")
    st.caption("Interfaz especializada para relaciones, habitaciones conectadas y recomendaciones en grafo.")

    if not neo4j_service.ping():
        st.error("No se pudo conectar a Neo4j en bolt://localhost:7687.")
        st.stop()

    show_dashboard()

    explore_tab, recommendations_tab = st.tabs(
        ["Explorar grafo", "Recomendaciones"]
    )
    with explore_tab:
        show_graph_explorer_tab()
    with recommendations_tab:
        show_recommendations_tab()


if __name__ == "__main__":
    main()
