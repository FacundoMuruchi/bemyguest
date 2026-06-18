from datetime import date, datetime

import pandas as pd
import streamlit as st
from cassandra.cluster import NoHostAvailable


CASSANDRA_IMPORT_ERROR = None

try:
    from cassandradb.cassandra import (
        DATASET_MODELS,
        crear_tablas,
        obtener_amenities_por_habitacion,
        obtener_calificaciones_por_resena,
        obtener_habitaciones_por_hotel,
        obtener_hoteles_por_pais,
        obtener_resenas_por_hotel,
    )
except NoHostAvailable as error:
    CASSANDRA_IMPORT_ERROR = error


TABLE_LABELS = {
    "hoteles_por_pais": "Hoteles por pais",
    "resenas_por_hotel_fecha": "Resenas por hotel y fecha",
    "calificaciones_por_resena": "Calificaciones por resena",
    "habitaciones_por_hotel": "Habitaciones por hotel",
    "amenities_por_habitacion": "Amenities por habitacion",
}


def serialize_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    return value


def rows_to_docs(rows):
    return [serialize_value(dict(row)) for row in rows]


def ensure_cassandra_ready():
    if CASSANDRA_IMPORT_ERROR is not None:
        st.error("No se pudo conectar a Cassandra en localhost:9042.")
        st.stop()


def get_counts():
    return {
        TABLE_LABELS.get(table_name, table_name): model.objects.count()
        for table_name, model in DATASET_MODELS.items()
    }


def show_dashboard():
    counts = get_counts()
    columns = st.columns(len(counts))
    for column, (name, count) in zip(columns, counts.items()):
        column.metric(name, count)


def show_docs(docs):
    if not docs:
        st.info("No se encontraron resultados.")
        return

    st.dataframe(pd.json_normalize(docs), use_container_width=True, hide_index=True)
    with st.expander("JSON"):
        st.json(docs)


def show_table_explorer():
    st.subheader("Explorar tablas")

    table_name = st.selectbox(
        "Tabla",
        list(DATASET_MODELS.keys()),
        format_func=lambda name: TABLE_LABELS.get(name, name),
    )
    limit = st.slider("Cantidad maxima", min_value=5, max_value=100, value=20, step=5)
    view_mode = st.radio("Vista", ["Tabla", "JSON"], horizontal=True)

    if st.button("Cargar registros", type="primary"):
        rows = DATASET_MODELS[table_name].objects.all().limit(limit)
        docs = rows_to_docs(rows)

        if not docs:
            st.info("No hay registros para mostrar.")
            return

        if view_mode == "Tabla":
            st.dataframe(pd.json_normalize(docs), use_container_width=True, hide_index=True)
        else:
            st.json(docs)


def show_query_results(rows):
    show_docs(rows_to_docs(rows))


def show_cassandra_queries():
    st.subheader("Consultas Cassandra")

    consulta = st.selectbox(
        "Seleccionar consulta",
        [
            "Hoteles por pais",
            "Resenas por hotel",
            "Calificaciones por resena",
            "Habitaciones por hotel",
            "Amenities por habitacion",
        ],
    )

    if consulta == "Hoteles por pais":
        pais = st.text_input("Pais")
        if st.button("Buscar hoteles"):
            show_query_results(obtener_hoteles_por_pais(pais))

    elif consulta == "Resenas por hotel":
        hotel_id = st.text_input("Hotel ID")
        if st.button("Buscar resenas"):
            show_query_results(obtener_resenas_por_hotel(hotel_id))

    elif consulta == "Calificaciones por resena":
        col_a, col_b = st.columns(2)
        hotel_id = col_a.text_input("Hotel ID")
        resena_id = col_b.text_input("Resena ID")
        if st.button("Buscar calificaciones"):
            show_query_results(obtener_calificaciones_por_resena(resena_id, hotel_id))

    elif consulta == "Habitaciones por hotel":
        hotel_id = st.text_input("Hotel ID")
        if st.button("Buscar habitaciones"):
            show_query_results(obtener_habitaciones_por_hotel(hotel_id))

    else:
        col_a, col_b = st.columns(2)
        hotel_id = col_a.text_input("Hotel ID")
        habitacion_id = col_b.text_input("Habitacion ID")
        if st.button("Buscar amenities"):
            show_query_results(obtener_amenities_por_habitacion(habitacion_id, hotel_id))


def main():
    st.set_page_config(page_title="BeMyGuest - Cassandra", layout="wide", page_icon="DB")

    st.title("BeMyGuest Cassandra")
    st.caption(
        "Interfaz solo de consulta para tablas query-driven. "
        "Las altas, bajas e importaciones se sincronizan desde mongo_app.py mediante el controlador multi-motor."
    )

    ensure_cassandra_ready()

    try:
        crear_tablas()
        show_dashboard()
    except NoHostAvailable:
        st.error("No se pudo conectar a Cassandra en localhost:9042.")
        st.stop()

    explore_tab, query_tab = st.tabs(["Explorar tablas", "Consultas"])

    with explore_tab:
        show_table_explorer()

    with query_tab:
        show_cassandra_queries()


if __name__ == "__main__":
    main()
