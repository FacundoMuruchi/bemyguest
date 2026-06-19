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
    page_title="BeMyGuest - REDIS",
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
            elif "sesion" in key:
                tipo = "🔑 Sesión Activa"
                significado = f"Usuario ID: {val}"
            else:
                tipo = "Otra"
                significado = str(val)

            all_keys.append({
                "Llave en Redis": key,
                "Tipo": tipo,
                "Valor": val,
                "Significado / Estado": significado,
                "TTL / Expiración": ttl_str
            })
            
    return all_keys


# --- RENDER PRINCIPAL ---

st.title("BeMyGuest — Redis")
st.caption("Panel para demostrar las capacidades en memoria de Redis (concurrencia, locks y TTLs).")

# --- BANNER DE MENSAJES DEL SANDBOX ---
if "sandbox_success" in st.session_state:
    st.success(st.session_state.pop("sandbox_success"))
if "sandbox_error" in st.session_state:
    st.error(st.session_state.pop("sandbox_error"))

# --- BARRA LATERAL (SESIONES) ---
with st.sidebar:
    st.title("🔑 Pruebas de Sesión")
    st.write("Podés iniciar sesión acá para ver cómo aparece el token en Redis en tiempo real.")
    
    token = st.session_state.get("session_token")
    logged_in_user_id = None
    
    if token:
        logged_in_user_id = redis_service.obtener_sesion(token)
        if not logged_in_user_id:
            st.session_state.pop("session_token")
            st.warning("Tu sesión ha expirado en Redis.")
            
    if logged_in_user_id:
        try:
            usr_doc = mongo.col_usuarios.find_one({"_id": ObjectId(logged_in_user_id)})
            if usr_doc:
                st.success(f"Logueado como: {usr_doc.get('nombre')} {usr_doc.get('apellido')}")
                
                # Mostrar datos crudos de la sesión
                ttl_sesion = redis_service.r.ttl(f"sesion:{token}")
                st.info(
                    f"**Datos Técnicos de la Sesión:**\n\n"
                    f"- **Token UUID:** `{token}`\n"
                    f"- **Llave en Redis:** `sesion:{token}`\n"
                    f"- **Valor (User ID):** `{logged_in_user_id}`\n"
                    f"- **Expira en:** `{ttl_sesion} segundos`"
                )
                
                if st.button("Cerrar Sesión", use_container_width=True):
                    redis_service.cerrar_sesion(token)
                    st.session_state.pop("session_token")
                    st.rerun()
        except Exception:
            pass
    else:
        try:
            usuarios_db = list(mongo.col_usuarios.find({}, {"_id": 1, "nombre": 1, "apellido": 1}))
            if usuarios_db:
                selected_user = st.selectbox(
                    "Iniciar sesión como:", 
                    usuarios_db, 
                    format_func=lambda u: f"{u.get('nombre')} {u.get('apellido')}",
                    key="login_sandbox_select"
                )
                if st.button("Iniciar Sesión", type="primary", use_container_width=True):
                    new_token = redis_service.iniciar_sesion(str(selected_user["_id"]))
                    st.session_state["session_token"] = new_token
                    st.toast("✅ Sesión iniciada en Redis.")
                    st.rerun()
            else:
                st.info("No hay usuarios en MongoDB para iniciar sesión.")
        except Exception:
            pass

# --- CONEXIÓN DIAGNÓSTICO ---
redis_online = redis_service.ping()

if not redis_online:
    st.error("🔴 **Redis está Desconectado**")
    st.info("Asegúrate de que tu servidor Redis está corriendo en `localhost:6379`. Puedes iniciarlo con Docker.")
    st.stop()
else:
    st.success("🟢 **Conectado con éxito a Redis en localhost:6379**")

# --- MÉTRICAS RÁPIDAS ---
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    total_keys = len(redis_service.r.keys("habitacion:*:disponible"))
    st.metric("Habitaciones registradas en Redis", total_keys)
with col_m2:
    total_locks = len(redis_service.r.keys("lock:habitacion:*"))
    st.metric("Locks temporales activos", total_locks)
with col_m3:
    reservas_hoy = redis_service.get_reservas_hoy()
    st.metric("Contador de Reservas Hoy (`stats`)", reservas_hoy)
with col_m4:
    total_sesiones = len(redis_service.r.keys("sesion:*"))
    st.metric("Sesiones Activas", total_sesiones)

st.divider()

# --- DISEÑO EN COLUMNAS: SIMULADOR Y TABLA EN VIVO ---
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("Simulador de Concurrencia y Locks")
    st.write("Usa este panel para simular reservas concurrentes.")
    
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
        
        # Simular Flujo de Reserva
        st.markdown("**Simular Proceso de Reserva:**")
        
        # Lógica de estado basada en la caché de Redis
        if lock_owner_cache == usr_id:
            # El usuario actual tiene el lock temporal
            st.success("🔒 ¡Lock adquirido! Estás en proceso de reserva (Revisá la tabla a la derecha).")
            col_conf1, col_conf2 = st.columns(2)
            with col_conf1:
                if st.button("Paso 2: Confirmar Pago y Completar", type="primary", use_container_width=True):
                    # Simulamos el commit en BD y actualizamos Redis
                    redis_service.set_disponible(hab_id, False)
                    redis_service.liberar_lock(hab_id)
                    redis_service.incrementar_reservas_hoy()
                    st.session_state["sandbox_success"] = "🎉 ¡Reserva confirmada! Habitación marcada como no disponible, stats actualizados y lock liberado."
                    st.rerun()
            with col_conf2:
                if st.button("Cancelar (Liberar Lock)", use_container_width=True):
                    redis_service.liberar_lock(hab_id)
                    st.session_state["sandbox_error"] = "🔓 Reserva cancelada. Se liberó el lock."
                    st.rerun()
        else:
            # El usuario actual NO tiene el lock
            if not disponibilidad_cache:
                st.error("❌ La habitación seleccionada ya fue reservada (No disponible).")
                if st.button("Resetear Disponibilidad (Modo Administrador)", use_container_width=True):
                    redis_service.set_disponible(hab_id, True)
                    st.rerun()
            elif lock_owner_cache:
                st.warning(f"⚠️ La habitación está bloqueada por el usuario: {lock_owner_cache}. Esperá a que expire el lock o libere.")
                if st.button("Forzar liberación de Lock (Modo Administrador)", use_container_width=True):
                    redis_service.liberar_lock(hab_id)
                    st.rerun()
            else:
                st.info("🟢 Habitación libre. Podés iniciar el proceso de reserva.")
                if st.button("Paso 1: Iniciar Reserva (Bloquear Habitación)", type="primary", use_container_width=True):
                    exito = redis_service.adquirir_lock(hab_id, usr_id, ttl_segundos=120)
                    if exito:
                        st.session_state["sandbox_success"] = f"🔒 Lock de 120s adquirido por el usuario {usr_id}. ¡Mirá la tabla a la derecha!"
                    else:
                        st.session_state["sandbox_error"] = "❌ Fallo de concurrencia: Alguien más ganó el lock."
                    st.rerun()


with col_right:
    st.subheader("Inspección y Visualización de Keys en Tiempo Real")
    st.write("Esta tabla lee en vivo el servidor de Redis. Podes ver cómo cambian las llaves, los valores y cómo se descuentan los segundos del TTL.")
    
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
        # Agrupar llaves por tipo para mejor visualización
        sesiones = [k for k in keys_data if "🔑 Sesión Activa" in k["Tipo"]]
        locks = [k for k in keys_data if "🔒 Bloqueo" in k["Tipo"]]
        stats = [k for k in keys_data if "📈 Contador" in k["Tipo"]]
        disponibilidad = [k for k in keys_data if "🟢 Disponibilidad" in k["Tipo"]]
        
        # Crear pestañas
        tab_disp, tab_locks, tab_ses, tab_stats = st.tabs([
            f"🟢 Disponibilidad ({len(disponibilidad)})", 
            f"🔒 Locks ({len(locks)})", 
            f"🔑 Sesiones ({len(sesiones)})", 
            f"📈 Stats Reservas ({len(stats)})"
        ])
        
        with tab_disp:
            if disponibilidad:
                st.dataframe(disponibilidad, use_container_width=True, hide_index=True)
            else:
                st.info("No hay llaves de disponibilidad. Probá sincronizar desde MongoDB.")
                
        with tab_locks:
            if locks:
                st.dataframe(locks, use_container_width=True, hide_index=True)
            else:
                st.info("No hay locks temporales de reserva activos en este momento.")
                
        with tab_ses:
            if sesiones:
                st.dataframe(sesiones, use_container_width=True, hide_index=True)
            else:
                st.info("No hay sesiones de usuarios activas.")
                
        with tab_stats:
            if stats:
                st.dataframe(stats, use_container_width=True, hide_index=True)
            else:
                st.info("No hay contadores ni estadísticas registradas.")
