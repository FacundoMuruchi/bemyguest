from contextlib import redirect_stdout
from datetime import date, datetime
from io import StringIO
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from cassandra.cluster import NoHostAvailable


DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / "mock_data" / "bemyguest_dataset.json"

CASSANDRA_IMPORT_ERROR = None

try:
    from cassandradb.cassandra import (
        DATASET_MODELS,
        crear_tablas,
        eliminar_todos_documentos,
        importar_dataset_json,
        obtener_amenities_por_habitacion,
        obtener_calificaciones_por_resena,
        obtener_habitaciones_por_hotel,
        obtener_hoteles_por_pais,
        obtener_resenas_por_hotel,
        registrar_habitacion,
        registrar_hotel,
        registrar_resena,
        to_int,
    )
    from cassandradb.models import (
        AmenitiesPorHabitacion,
        CalifacionPorResena,
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

ROOM_TYPES = ["estandar", "superior", "suite", "cabaña"]
BED_OPTIONS = ["individual", "doble", "queen", "king size"]
VIEW_OPTIONS = ["jardín", "calle", "montaña", "lago", "mar"]


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
    return [
        serialize_value(dict(row))
        for row in rows
    ]


def run_engine_action(action):
    output = StringIO()
    with redirect_stdout(output):
        result = action()
    text = output.getvalue().strip()
    return result, text


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


def show_hotel_form():
    with st.form("cassandra_hotel_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        pais = col_a.text_input("Pais")
        hotel_id = col_b.text_input("Hotel ID")
        nombre = st.text_input("Nombre")
        col_c, col_d, col_e = st.columns(3)
        ciudad = col_c.text_input("Ciudad")
        categoria = col_d.number_input("Categoria", min_value=1, max_value=5, value=3)
        calificacion_promedio = col_e.slider("Calificacion promedio", 1.0, 5.0, 4.0, 0.1)

        if st.form_submit_button("Registrar hotel por pais", type="primary"):
            registrar_hotel(
                {
                    "_id": hotel_id,
                    "pais": pais,
                    "nombre": nombre,
                    "ciudad": ciudad,
                    "categoria": categoria,
                    "calificacion_promedio": calificacion_promedio,
                }
            )
            st.session_state["last_success"] = "Hotel registrado en hoteles_por_pais."
            st.rerun()


def show_room_form():
    with st.form("cassandra_room_form", clear_on_submit=True):
        col_a, col_b, col_c = st.columns(3)
        hotel_id = col_a.text_input("Hotel ID")
        habitacion_id = col_b.text_input("Habitacion ID")
        numero = col_c.text_input("Numero")
        col_d, col_e, col_f = st.columns(3)
        tipo = col_d.selectbox("Tipo", ROOM_TYPES)
        capacidad_adultos = col_e.number_input("Capacidad adultos", min_value=1, max_value=10, value=2)
        precio_por_noche = col_f.number_input("Precio por noche", min_value=0.0, value=10000.0, step=500.0)

        st.subheader("Amenities")
        col_g, col_h, col_i = st.columns(3)
        cama = col_g.selectbox("Cama", BED_OPTIONS)
        metros_cuadrados = col_h.number_input("Metros cuadrados", min_value=1, max_value=300, value=25)
        vista = col_i.selectbox("Vista", VIEW_OPTIONS)
        col_j, col_k, col_l, col_m = st.columns(4)
        tv_smart = col_j.checkbox("TV smart", value=True)
        aire_acondicionado = col_k.checkbox("Aire acondicionado")
        jacuzzi = col_l.checkbox("Jacuzzi")
        terraza = col_m.checkbox("Terraza")

        if st.form_submit_button("Registrar habitacion", type="primary"):
            registrar_habitacion(
                {
                    "_id": habitacion_id,
                    "hotel_id": hotel_id,
                    "numero": numero,
                    "tipo": tipo,
                    "capacidad_adultos": capacidad_adultos,
                    "precio_por_noche": precio_por_noche,
                    "amenities": {
                        "cama": cama,
                        "metros_cuadrados": metros_cuadrados,
                        "vista": vista,
                        "tv_smart": tv_smart,
                        "aire_acondicionado": aire_acondicionado,
                        "jacuzzi": jacuzzi,
                        "terraza": terraza,
                    },
                }
            )
            st.session_state["last_success"] = "Habitacion registrada en Cassandra."
            st.rerun()


def show_review_form():
    with st.form("cassandra_review_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        hotel_id = col_a.text_input("Hotel ID")
        resena_id = col_b.text_input("Resena ID")
        usuario_id = st.text_input("Usuario ID")
        col_c, col_d, col_e, col_f = st.columns(4)
        general = col_c.slider("General", 1, 5, 4)
        limpieza = col_d.slider("Limpieza", 1, 5, 4)
        atencion = col_e.slider("Atencion", 1, 5, 4)
        ubicacion = col_f.slider("Ubicacion", 1, 5, 4)
        comentario = st.text_area("Comentario")
        fecha = st.date_input("Fecha", value=date.today())

        if st.form_submit_button("Registrar resena", type="primary"):
            registrar_resena(
                {
                    "_id": resena_id,
                    "hotel_id": hotel_id,
                    "usuario_id": usuario_id,
                    "fecha": fecha,
                    "comentario": comentario,
                    "calificacion": {
                        "general": general,
                        "limpieza": limpieza,
                        "atencion": atencion,
                        "ubicacion": ubicacion,
                    },
                }
            )
            st.session_state["last_success"] = "Resena registrada en Cassandra."
            st.rerun()


def show_amenity_form():
    with st.form("cassandra_amenity_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        hotel_id = col_a.text_input("Hotel ID")
        habitacion_id = col_b.text_input("Habitacion ID")
        amenity_nombre = st.text_input("Amenity")
        descripcion = st.text_input("Descripcion")

        if st.form_submit_button("Registrar amenity", type="primary"):
            AmenitiesPorHabitacion.create(
                hotel_id=hotel_id,
                habitacion_id=habitacion_id,
                amenity_nombre=amenity_nombre,
                descripcion=descripcion,
            )
            st.session_state["last_success"] = "Amenity registrado en Cassandra."
            st.rerun()


def show_rating_form():
    with st.form("cassandra_rating_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        hotel_id = col_a.text_input("Hotel ID")
        resena_id = col_b.text_input("Resena ID")
        calificacion_nombre = st.text_input("Calificacion")
        puntuacion = st.number_input("Puntuacion", min_value=1, max_value=5, value=4)

        if st.form_submit_button("Registrar calificacion", type="primary"):
            CalifacionPorResena.create(
                hotel_id=hotel_id,
                resena_id=resena_id,
                calificacion_nombre=calificacion_nombre,
                puntuacion=to_int(puntuacion),
            )
            st.session_state["last_success"] = "Calificacion registrada en Cassandra."
            st.rerun()


def show_manual_registration():
    st.subheader("Registrar documento Cassandra")
    option = st.selectbox(
        "Modelo",
        [
            "Hotel por pais",
            "Habitacion",
            "Amenity por habitacion",
            "Resena",
            "Calificacion por resena",
        ],
    )

    if option == "Hotel por pais":
        show_hotel_form()
    elif option == "Habitacion":
        show_room_form()
    elif option == "Amenity por habitacion":
        show_amenity_form()
    elif option == "Resena":
        show_review_form()
    else:
        show_rating_form()


def show_query_results(rows):
    docs = rows_to_docs(rows)
    if not docs:
        st.info("No se encontraron resultados.")
        return

    st.dataframe(pd.DataFrame(docs), use_container_width=True, hide_index=True)
    with st.expander("JSON"):
        st.json(docs)


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


def show_import_tab():
    st.subheader("Importar dataset")
    st.code(str(DEFAULT_DATASET_PATH), language="text")
    st.caption("La importacion reemplaza las filas actuales de las tablas Cassandra.")

    if st.button("Importar dataset", type="primary"):
        try:
            counts, output = run_engine_action(
                lambda: importar_dataset_json(DEFAULT_DATASET_PATH, reset_first=True)
            )
        except FileNotFoundError:
            st.error(f"No se encontro el dataset en {DEFAULT_DATASET_PATH}.")
        except (ValueError, json.JSONDecodeError) as error:
            st.error(f"El dataset no es valido: {error}")
        else:
            st.session_state["last_success"] = "Dataset importado en Cassandra."
            st.session_state["last_output"] = output
            st.session_state["last_counts"] = counts
            st.rerun()

    if "last_counts" in st.session_state:
        st.json(st.session_state.pop("last_counts"))


def show_admin_tab():
    st.subheader("Mantenimiento")

    if st.button("Sincronizar tablas", type="primary"):
        _, output = run_engine_action(crear_tablas)
        st.session_state["last_success"] = "Tablas sincronizadas."
        st.session_state["last_output"] = output
        st.rerun()

    st.divider()
    selected = st.multiselect(
        "Tablas a limpiar",
        list(DATASET_MODELS.keys()),
        format_func=lambda name: TABLE_LABELS.get(name, name),
    )
    confirm = st.checkbox("Confirmo que quiero eliminar los registros seleccionados")

    if st.button("Eliminar registros", disabled=not selected or not confirm):
        for table_name in selected:
            eliminar_todos_documentos(DATASET_MODELS[table_name])
        st.session_state["last_success"] = "Registros eliminados."
        st.rerun()


def main():
    st.set_page_config(page_title="BeMyGuest Cassandra", layout="wide")

    st.title("BeMyGuest Cassandra")
    st.caption("Interfaz para cargar, consultar y administrar las tablas query-driven de Cassandra.")

    ensure_cassandra_ready()

    try:
        crear_tablas()
        show_dashboard()
    except NoHostAvailable:
        st.error("No se pudo conectar a Cassandra en localhost:9042.")
        st.stop()

    if "last_success" in st.session_state:
        st.success(st.session_state.pop("last_success"))
    if "last_output" in st.session_state:
        output = st.session_state.pop("last_output")
        if output:
            st.code(output, language="text")

    explore_tab, create_tab, query_tab, import_tab, admin_tab = st.tabs(
        [
            "Explorar tablas",
            "Registrar documento",
            "Consultas",
            "Cargar datos",
            "Administrar",
        ]
    )

    with explore_tab:
        show_table_explorer()

    with create_tab:
        show_manual_registration()

    with query_tab:
        show_cassandra_queries()

    with import_tab:
        show_import_tab()

    with admin_tab:
        show_admin_tab()


if __name__ == "__main__":
    main()
