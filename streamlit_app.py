from contextlib import redirect_stdout
from datetime import date, timedelta
from io import StringIO
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from bson import ObjectId
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from mongodb import mongo


DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / "mock_data" / "bemyguest_dataset.json"

COLLECTIONS = {
    "Usuarios": mongo.col_usuarios,
    "Hoteles": mongo.col_hoteles,
    "Habitaciones": mongo.col_habitaciones,
    "Reservas": mongo.col_reservas,
    "Reseñas": mongo.col_resenas,
}

SERVICE_OPTIONS = ["wifi", "pileta", "spa", "estacionamiento", "gimnasio", "restaurante"]
EXTRA_SERVICE_OPTIONS = ["desayuno", "media_pension", "pension_completa", "transfer", "city_tour"]
ROOM_TYPES = ["estandar", "superior", "suite", "cabaña"]
BED_OPTIONS = ["individual", "doble", "queen", "king size"]
VIEW_OPTIONS = ["jardín", "calle", "montaña", "lago", "mar"]


def serialize_value(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    return value


def serialize_docs(docs):
    return [serialize_value(doc) for doc in docs]


def run_engine_action(action):
    output = StringIO()
    with redirect_stdout(output):
        action()
    return output.getvalue().strip()


def ping_database():
    mongo.client.admin.command("ping")


def get_counts():
    return {
        name: collection.count_documents({})
        for name, collection in COLLECTIONS.items()
    }


def delete_all_data():
    for collection in COLLECTIONS.values():
        mongo.eliminar_todos_documentos(collection)


def import_dataset(dataset_path=DEFAULT_DATASET_PATH):
    def action():
        counts = mongo.importar_dataset_json(dataset_path, reset_first=True)
        print(f"Dataset importado desde {dataset_path}")
        print(f"Total registros: {sum(counts.values())}")
        for collection_name, count in counts.items():
            print(f"- {collection_name}: {count}")

    return run_engine_action(action)


def load_docs(collection, projection=None):
    return list(collection.find({}, projection).sort("_id", -1))


def user_label(usuario):
    return f"{usuario.get('nombre', '')} {usuario.get('apellido', '')} | {usuario.get('email', '')}"


def hotel_label(hotel):
    return f"{hotel.get('nombre', 'Hotel sin nombre')} | {hotel.get('ciudad', 'Sin ciudad')}, {hotel.get('pais', 'Sin país')}"


def room_label(habitacion):
    estado = "disponible" if habitacion.get("disponible") else "no disponible"
    return f"Habitación {habitacion.get('numero', 's/n')} | {habitacion.get('tipo', 'sin tipo')} | {estado}"


def parse_extra_attributes(raw_extra_attributes):
    raw_extra_attributes = raw_extra_attributes.strip()
    if not raw_extra_attributes:
        return {}

    try:
        extra_attributes = json.loads(raw_extra_attributes)
    except json.JSONDecodeError as error:
        st.error(f"Los atributos adicionales no tienen un JSON válido: {error.msg}")
        return None

    if not isinstance(extra_attributes, dict):
        st.error("Los atributos adicionales deben ser un objeto JSON, por ejemplo: {\"origen\": \"web\"}.")
        return None
    if "_id" in extra_attributes:
        st.error("No se puede definir manualmente el atributo _id desde la interfaz.")
        return None
    return extra_attributes


def merge_extra_attributes(document, raw_extra_attributes):
    extra_attributes = parse_extra_attributes(raw_extra_attributes)
    if extra_attributes is None:
        return None
    return {**document, **extra_attributes}


def save_document(collection, document):
    inserted = collection.insert_one(document)
    st.session_state["last_success"] = f"Documento registrado correctamente con _id {inserted.inserted_id}."
    st.rerun()


def build_filter(collection_name, search_text):
    if not search_text:
        return {}

    regex = {"$regex": search_text, "$options": "i"}
    searchable_fields = {
        "Usuarios": ["nombre", "apellido", "email", "telefono", "pais", "ciudad"],
        "Hoteles": ["nombre", "ciudad", "pais", "servicios"],
        "Habitaciones": ["numero", "tipo", "amenities.vista", "amenities.cama"],
        "Reservas": ["usuario_id", "estado", "servicios_extra"],
        "Reseñas": ["usuario_id", "comentario"],
    }
    return {"$or": [{field: regex} for field in searchable_fields[collection_name]]}


def show_collection(collection_name, limit, search_text):
    collection = COLLECTIONS[collection_name]
    query = build_filter(collection_name, search_text)
    docs = serialize_docs(collection.find(query).limit(limit))

    if not docs:
        st.info("No hay documentos para mostrar con esos filtros.")
        return

    view_mode = st.radio(
        "Vista",
        ["Tabla", "JSON"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if view_mode == "Tabla":
        st.dataframe(pd.json_normalize(docs), use_container_width=True, hide_index=True)
    else:
        st.json(docs)


def show_extra_attributes_help():
    return st.text_area(
        "Atributos adicionales en JSON",
        placeholder='{"observaciones": "Carga manual", "activo": true}',
        help="Opcional. Se mezclan con el documento antes de guardarlo.",
    )


def show_user_form():
    with st.form("create_user_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        nombre = col_a.text_input("Nombre")
        apellido = col_b.text_input("Apellido")
        email = st.text_input("Email")
        col_c, col_d, col_e = st.columns(3)
        telefono = col_c.text_input("Teléfono")
        pais = col_d.text_input("País")
        ciudad = col_e.text_input("Ciudad")
        raw_extra_attributes = show_extra_attributes_help()

        if st.form_submit_button("Registrar usuario", type="primary"):
            document = {
                "nombre": nombre,
                "apellido": apellido,
                "email": email,
                "telefono": telefono,
                "pais": pais,
                "ciudad": ciudad,
            }
            document = merge_extra_attributes(document, raw_extra_attributes)
            if document is not None:
                save_document(mongo.col_usuarios, document)


def show_hotel_form():
    with st.form("create_hotel_form", clear_on_submit=True):
        nombre = st.text_input("Nombre")
        col_a, col_b, col_c = st.columns(3)
        ciudad = col_a.text_input("Ciudad")
        pais = col_b.text_input("País")
        categoria = col_c.number_input("Categoría", min_value=1, max_value=5, value=3)
        servicios = st.multiselect("Servicios", SERVICE_OPTIONS, default=["wifi"])
        calificacion_promedio = st.slider("Calificación promedio", 1.0, 5.0, 4.0, 0.1)
        raw_extra_attributes = show_extra_attributes_help()

        if st.form_submit_button("Registrar hotel", type="primary"):
            document = {
                "nombre": nombre,
                "ciudad": ciudad,
                "pais": pais,
                "categoria": categoria,
                "servicios": servicios,
                "calificacion_promedio": calificacion_promedio,
            }
            document = merge_extra_attributes(document, raw_extra_attributes)
            if document is not None:
                save_document(mongo.col_hoteles, document)


def show_room_form():
    hoteles = load_docs(mongo.col_hoteles)
    if not hoteles:
        st.info("Primero registrá al menos un hotel para poder asociar la habitación.")
        return

    with st.form("create_room_form", clear_on_submit=True):
        hotel = st.selectbox("Hotel", hoteles, format_func=hotel_label)
        col_a, col_b, col_c = st.columns(3)
        numero = col_a.text_input("Número")
        tipo = col_b.selectbox("Tipo", ROOM_TYPES)
        capacidad_adultos = col_c.number_input("Capacidad adultos", min_value=1, max_value=10, value=2)
        col_d, col_e = st.columns(2)
        precio_por_noche = col_d.number_input("Precio por noche", min_value=0.0, value=10000.0, step=500.0)
        disponible = col_e.checkbox("Disponible", value=True)

        st.subheader("Amenities")
        col_f, col_g, col_h = st.columns(3)
        cama = col_f.selectbox("Cama", BED_OPTIONS)
        metros_cuadrados = col_g.number_input("Metros cuadrados", min_value=1, max_value=300, value=25)
        vista = col_h.selectbox("Vista", VIEW_OPTIONS)
        col_i, col_j, col_k, col_l = st.columns(4)
        tv_smart = col_i.checkbox("TV smart", value=True)
        aire_acondicionado = col_j.checkbox("Aire acondicionado")
        jacuzzi = col_k.checkbox("Jacuzzi")
        terraza = col_l.checkbox("Terraza")
        raw_extra_attributes = show_extra_attributes_help()

        if st.form_submit_button("Registrar habitación", type="primary"):
            document = {
                "hotel_id": hotel["_id"],
                "numero": numero,
                "tipo": tipo,
                "capacidad_adultos": capacidad_adultos,
                "precio_por_noche": precio_por_noche,
                "disponible": disponible,
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
            document = merge_extra_attributes(document, raw_extra_attributes)
            if document is not None:
                save_document(mongo.col_habitaciones, document)


def show_booking_form():
    usuarios = load_docs(mongo.col_usuarios)
    habitaciones = load_docs(mongo.col_habitaciones)
    if not usuarios or not habitaciones:
        st.info("Primero registrá usuarios y habitaciones para poder crear una reserva.")
        return

    with st.form("create_booking_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        usuario = col_a.selectbox("Usuario", usuarios, format_func=user_label)
        habitacion = col_b.selectbox("Habitación", habitaciones, format_func=room_label)
        capacidad_habitacion = int(habitacion.get("capacidad_adultos") or 1)
        col_c, col_d, col_e = st.columns(3)
        check_in = col_c.date_input("Check-in", value=date.today())
        check_out = col_d.date_input("Check-out", value=date.today() + timedelta(days=1))
        huespedes = col_e.number_input(
            "Huéspedes",
            min_value=1,
            max_value=capacidad_habitacion,
            value=min(2, capacidad_habitacion),
        )
        col_f, col_g = st.columns(2)
        estado = col_f.selectbox("Estado", mongo.ESTADOS)
        servicios_extra = col_g.multiselect("Servicios extra", EXTRA_SERVICE_OPTIONS)
        fecha_reserva = st.date_input("Fecha de reserva", value=date.today())
        raw_extra_attributes = show_extra_attributes_help()

        if st.form_submit_button("Registrar reserva", type="primary"):
            noches = (check_out - check_in).days
            if noches <= 0:
                st.error("La fecha de check-out debe ser posterior al check-in.")
                return
            if "hotel_id" not in habitacion:
                st.error("La habitación seleccionada no tiene hotel_id asociado.")
                return
            if huespedes > capacidad_habitacion:
                st.error("La cantidad de huéspedes no puede superar la capacidad de la habitación.")
                return

            document = {
                "usuario_id": usuario["_id"],
                "habitacion_id": habitacion["_id"],
                "hotel_id": habitacion["hotel_id"],
                "check_in": check_in.isoformat(),
                "check_out": check_out.isoformat(),
                "noches": noches,
                "huespedes": huespedes,
                "estado": estado,
                "servicios_extra": servicios_extra,
                "fecha_reserva": fecha_reserva.isoformat(),
            }
            document = merge_extra_attributes(document, raw_extra_attributes)
            if document is not None:
                save_document(mongo.col_reservas, document)


def show_review_form():
    usuarios = load_docs(mongo.col_usuarios)
    hoteles = load_docs(mongo.col_hoteles)
    if not usuarios or not hoteles:
        st.info("Primero registrá usuarios y hoteles para poder crear una reseña.")
        return

    with st.form("create_review_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        usuario = col_a.selectbox("Usuario", usuarios, format_func=user_label)
        hotel = col_b.selectbox("Hotel", hoteles, format_func=hotel_label)
        col_c, col_d, col_e, col_f = st.columns(4)
        general = col_c.slider("General", 1.0, 5.0, 4.0, 0.1)
        limpieza = col_d.slider("Limpieza", 1, 5, 4)
        atencion = col_e.slider("Atención", 1, 5, 4)
        ubicacion = col_f.slider("Ubicación", 1, 5, 4)
        comentario = st.text_area("Comentario")
        fecha = st.date_input("Fecha", value=date.today())
        raw_extra_attributes = show_extra_attributes_help()

        if st.form_submit_button("Registrar reseña", type="primary"):
            document = {
                "hotel_id": hotel["_id"],
                "usuario_id": usuario["_id"],
                "calificacion": {
                    "general": general,
                    "limpieza": limpieza,
                    "atencion": atencion,
                    "ubicacion": ubicacion,
                },
                "comentario": comentario,
                "fecha": fecha.isoformat(),
            }
            document = merge_extra_attributes(document, raw_extra_attributes)
            if document is not None:
                save_document(mongo.col_resenas, document)


def show_manual_registration():
    collection_name = st.selectbox(
        "Colección a registrar",
        list(COLLECTIONS.keys()),
        key="create_collection_name",
    )

    form_renderers = {
        "Usuarios": show_user_form,
        "Hoteles": show_hotel_form,
        "Habitaciones": show_room_form,
        "Reservas": show_booking_form,
        "Reseñas": show_review_form,
    }
    form_renderers[collection_name]()


def show_dashboard():
    counts = get_counts()
    columns = st.columns(len(counts))
    for column, (name, count) in zip(columns, counts.items()):
        column.metric(name, count)


def main():
    st.set_page_config(page_title="BeMyGuest", layout="wide")

    st.title("BeMyGuest")
    st.caption("Interfaz simple para cargar, consultar y administrar usuarios, hoteles, habitaciones, reservas y reseñas en MongoDB.")

    try:
        ping_database()
    except ServerSelectionTimeoutError:
        st.error("No se pudo conectar a MongoDB en localhost:27017.")
        st.stop()

    show_dashboard()
    if "last_success" in st.session_state:
        st.success(st.session_state.pop("last_success"))
    if "last_output" in st.session_state:
        output = st.session_state.pop("last_output")
        if output:
            st.code(output, language="text")

    explore_tab, create_tab, seed_tab, admin_tab = st.tabs(
        ["Explorar datos", "Registrar documento", "Cargar datos", "Administrar"]
    )

    with explore_tab:
        left, right = st.columns([1, 2])
        with left:
            collection_name = st.selectbox("Colección", list(COLLECTIONS.keys()))
            search_text = st.text_input("Buscar", placeholder="Ciudad, usuario, email, estado, tipo...")
            limit = st.slider("Cantidad máxima", min_value=5, max_value=100, value=20, step=5)
        with right:
            show_collection(collection_name, limit, search_text)

    with create_tab:
        st.subheader("Registrar documento")
        show_manual_registration()

    with seed_tab:
        st.subheader("Importar dataset")
        st.code(str(DEFAULT_DATASET_PATH), language="text")
        st.caption("La importación reemplaza los documentos actuales de las colecciones principales.")

        if st.button("Importar dataset", type="primary"):
            try:
                output = import_dataset()
            except FileNotFoundError:
                st.error(f"No se encontró el dataset en {DEFAULT_DATASET_PATH}.")
            except (ValueError, json.JSONDecodeError) as error:
                st.error(f"El dataset no es válido: {error}")
            except PyMongoError as error:
                st.error(f"No se pudo importar el dataset en MongoDB: {error}")
            else:
                st.session_state["last_success"] = "Dataset importado correctamente."
                st.session_state["last_output"] = output
                st.rerun()

        st.divider()
        st.subheader("Cargar dataset externo (Hoteles)")
        st.info("El archivo JSON debe contener una lista de objetos, idealmente respetando los campos: nombre, ciudad, pais, categoria, servicios y calificacion_promedio.")
        uploaded_file = st.file_uploader("Subir archivo JSON de hoteles", type=["json"])
        
        if st.button("Importar dataset", type="primary"):
            if uploaded_file is not None:
                datos_hoteles = json.load(uploaded_file)
                mongo.insertar_hoteles_desde_lista(datos_hoteles)
                st.session_state["last_success"] = f"{len(datos_hoteles)} hoteles importados exitosamente desde el archivo."
                st.rerun()
            else:
                st.error("Por favor, subí un archivo JSON primero.")

    with admin_tab:
        st.subheader("Mantenimiento")
        selected = st.multiselect(
            "Colecciones a limpiar",
            list(COLLECTIONS.keys()),
            default=[],
        )
        confirm = st.checkbox("Confirmo que quiero eliminar los documentos seleccionados")

        if st.button("Eliminar documentos", disabled=not selected or not confirm):
            for name in selected:
                mongo.eliminar_todos_documentos(COLLECTIONS[name])
            st.session_state["last_success"] = "Documentos eliminados."
            st.rerun()


if __name__ == "__main__":
    main()
