# redis_app.py
"""
Aplicación Streamlit complementaria que funciona como un "Redis Sandbox".
Permite visualizar llaves en tiempo real, auditar TTLs, simular concurrencia,
y gestionar bloqueos atómicos de forma visual e interactiva.

Uso:
    uv run streamlit run redis_app.py
"""

import streamlit as st
from bson import ObjectId
from mongodb import mongo
from redis_service import redis_service

# Configuración de página premium
st.set_page_config(
    page_title="BeMyGuest - Redis Sandbox",
    page_icon="⚡",
    layout="wide"
)


# --- HELPERS DE INTERFAZ ---

def get_keys_summary():
    """Escanea y formatea todas las llaves activas de BeMyGuest en Redis."""
    client = redis_service.r
    patterns = [
        "habitacion:*:disponible",
        "lock:habitacion:*",
        "stats:reservas:*",
        "sesion:*"
    ]
    
    all_keys = []
    for pattern in patterns:
        keys = client.keys(pattern)
        for key in keys:
            ttl = client.ttl(key)
            val = client.get(key)
            
            # Formatear el TTL de forma amigable
            if ttl == -1:
                ttl_str = "♾️ No expira"
            elif ttl == -2:
                ttl_str = "❌ Expirado"
            else:
                ttl_str = f"⏳ {ttl} segundos"
                
            # Identificar el tipo de clave
            if "disponible" in key:
                tipo = "🟢 Disponibilidad (String)"
                significado = "Disponible (1)" if val == "1" else "No Disponible (0)"
            elif "lock" in key:
                tipo = "🔒 Bloqueo de Reserva (String con TTL)"
                significado = f"Bloqueado por Usuario: {val}"
            elif "stats" in key:
                tipo = "📈 Contador Estadístico"
                significado = f"Total reservas: {val}"
            else:
                tipo = "🔑 Sesión / Otra"
                significado = str(val)

            all_keys.append({
                "Llave en Redis": key,
                "Valor": val,
                "Significado / Estado": significado,
                "TTL / Expiración": ttl_str
            })
            
    return all_keys


# --- RENDER PRINCIPAL ---

st.title("⚡ BeMyGuest — Redis Sandbox & Auditor en Vivo")
st.caption("Panel de control exclusivo para depurar y demostrar las capacidades en memoria de Redis (concurrencia, locks y TTLs).")

# --- BANNER DE MENSAJES DEL SANDBOX ---
if "sandbox_success" in st.session_state:
    st.success(st.session_state.pop("sandbox_success"))
if "sandbox_error" in st.session_state:
    st.error(st.session_state.pop("sandbox_error"))

# --- CONEXIÓN DIAGNÓSTICO ---
redis_online = redis_service.ping()

if not redis_online:
    st.error("🔴 **Redis está Desconectado**")
    st.info("Asegúrate de que tu servidor Redis está corriendo en `localhost:6379`. Puedes iniciarlo con Docker o WSL.")
    st.stop()
else:
    st.success("🟢 **Conectado con éxito a Redis en localhost:6379**")

# --- MÉTRICAS RÁPIDAS ---
col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    total_keys = len(redis_service.r.keys("habitacion:*:disponible"))
    st.metric("Habitaciones registradas en Redis", total_keys)
with col_m2:
    total_locks = len(redis_service.r.keys("lock:habitacion:*"))
    st.metric("Locks temporales activos", total_locks)
with col_m3:
    reservas_hoy = redis_service.get_reservas_hoy()
    st.metric("Contador de Reservas Hoy (`stats`)", reservas_hoy)

st.divider()

# --- DISEÑO EN COLUMNAS: SIMULADOR Y TABLA EN VIVO ---
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("🎮 Simulador de Concurrencia y Locks")
    st.write("Usa este panel para simular reservas concurrentes, colocar candados manuales o forzar cambios de disponibilidad.")
    
    # Cargar datos de MongoDB para los dropdowns
    try:
        usuarios = list(mongo.col_usuarios.find({}, {"_id": 1, "nombre": 1, "apellido": 1}))
        habitaciones = list(mongo.col_habitaciones.find({}, {"_id": 1, "numero": 1, "tipo": 1}))
    except Exception as e:
        st.error(f"No se pudo conectar a MongoDB para cargar usuarios y habitaciones: {e}")
        st.stop()

    if not usuarios or not habitaciones:
        st.warning("Asegúrate de importar el dataset en MongoDB primero para poder operar en el simulador.")
    else:
        # Selectores
        usuario = st.selectbox(
            "Seleccionar Usuario Simulante", 
            usuarios, 
            format_func=lambda u: f"{u.get('nombre')} {u.get('apellido')} | {u['_id']}"
        )
        habitacion = st.selectbox(
            "Seleccionar Habitación", 
            habitaciones, 
            format_func=lambda h: f"Habitación {h.get('numero')} ({h.get('tipo')}) | {h['_id']}"
        )
        
        hab_id = str(habitacion["_id"])
        usr_id = str(usuario["_id"])
        
        # Estado actual en Redis
        disponibilidad_cache = redis_service.is_disponible(hab_id)
        lock_owner_cache = redis_service.get_lock_owner(hab_id)
        
        st.write("---")
        st.write("**Estado actual en caché para la Habitación seleccionada:**")
        st.write(f"- 🟢 **Disponible**: `{'SÍ (1)' if disponibilidad_cache else 'NO (0)'}`")
        st.write(f"- 🔒 **Dueño del lock**: `{lock_owner_cache if lock_owner_cache else 'Ninguno (Sin candado)'}`")
        
        st.write("---")
        
        # Acciones interactivas
        st.markdown("**Acciones Atómicas de Redis:**")
        
        # 1. toggle disponibilidad
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Marcar como Disponible", use_container_width=True):
                redis_service.set_disponible(hab_id, True)
                st.session_state["sandbox_success"] = "🟢 Habitación marcada como disponible en Redis."
                st.rerun()
        with col_btn2:
            if st.button("Marcar como NO Disponible", use_container_width=True):
                redis_service.set_disponible(hab_id, False)
                st.session_state["sandbox_success"] = "🔴 Habitación marcada como NO disponible en Redis."
                st.rerun()

        st.write("")
        
        # 2. Lock temporal
        col_btn3, col_btn4 = st.columns(2)
        with col_btn3:
            if st.button("🔒 Intentar Adquirir Lock", type="primary", use_container_width=True):
                exito = redis_service.adquirir_lock(hab_id, usr_id, ttl_segundos=120)
                if exito:
                    st.session_state["sandbox_success"] = f"🔒 ¡Lock adquirido con éxito por 120s para el usuario {usr_id}!"
                else:
                    owner = redis_service.get_lock_owner(hab_id)
                    st.session_state["sandbox_error"] = f"❌ Fallo de concurrencia: Habitación ya bloqueada en Redis por {owner}."
                st.rerun()
        with col_btn4:
            if st.button("🔓 Liberar Lock Manual", use_container_width=True):
                redis_service.liberar_lock(hab_id)
                st.session_state["sandbox_success"] = "🔓 Candado temporal liberado con éxito en Redis."
                st.rerun()
                
        # 3. Métricas
        st.write("")
        st.markdown("**Métricas:**")
        if st.button("📈 Incrementar Reservas Hoy (+1)", use_container_width=True):
            redis_service.incrementar_reservas_hoy()
            st.session_state["sandbox_success"] = "📈 Contador stats:reservas:hoy incrementado exitosamente."
            st.rerun()


with col_right:
    st.subheader("🕵️ Inspección y Visualización de Llaves en Tiempo Real")
    st.write("Esta tabla lee en vivo el servidor de Redis. Puedes interactuar en el panel izquierdo y ver cómo cambian las llaves, los valores y cómo se descuentan los segundos del TTL en tiempo real.")
    
    col_ref, col_seed = st.columns([1, 1])
    with col_ref:
        if st.button("🔄 Refrescar Llaves", type="secondary", use_container_width=True):
            st.rerun()
    with col_seed:
        if st.button("⚙️ Sincronizar desde MongoDB (Seeding)", use_container_width=True):
            habitaciones_db = list(mongo.col_habitaciones.find({}))
            cantidad = redis_service.seed_from_habitaciones(habitaciones_db)
            st.session_state["sandbox_success"] = f"⚙️ Sincronización completada. {cantidad} habitaciones mapped a Redis."
            st.rerun()
            
    # Traer llaves estructuradas
    keys_data = get_keys_summary()
    
    if not keys_data:
        st.info("No hay llaves registradas en Redis para BeMyGuest. Presiona el botón de 'Sincronizar desde MongoDB' para poblar la base de datos en memoria.")
    else:
        st.dataframe(
            keys_data,
            use_container_width=True,
            hide_index=True
        )
