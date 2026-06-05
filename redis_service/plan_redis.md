# Plan de Implementación de Redis — BeMyGuest

## 1. Objetivo

Integrar Redis como motor complementario a MongoDB para gestionar **disponibilidad en tiempo real** y **bloqueos temporales de habitaciones** (anti-overbooking). Redis no reemplaza a Mongo: actúa como capa de estado rápido en memoria, mientras Mongo sigue siendo la fuente de verdad de los documentos.

---

## 2. Rol de Redis en la Arquitectura Multi-Motor

| Motor       | Responsabilidad                                          |
| :---------- | :------------------------------------------------------- |
| **MongoDB** | Documentos completos: usuarios, hoteles, habitaciones, reservas, reseñas |
| **Redis**   | Estado transitorio: disponibilidad y locks temporales    |
| **Neo4j**   | Relaciones persistentes y recomendaciones                |
| **Cassandra** | Eventos históricos inmutables                          |

Redis y Neo4j **no se pisan**: Redis opera *durante* el proceso de reserva (¿se puede reservar?), Neo4j opera *después* de confirmar (¿qué relaciones existen?).

---

## 3. Modelo de Datos (Key-Value Design)

Se usa la convención de `:` como separador de jerarquía. Los IDs son los `_id` de MongoDB serializados como string.

| Caso de Uso           | Key                              | Tipo     | TTL    | Descripción                                              |
| :-------------------- | :------------------------------- | :------- | :----- | :------------------------------------------------------- |
| **Disponibilidad**    | `habitacion:{id}:disponible`     | String   | No     | `"1"` = disponible, `"0"` = no disponible                |
| **Bloqueo temporal**  | `lock:habitacion:{id}`           | String   | 600s   | Valor = `usuario_id`. Evita overbooking durante el pago  |
| **Sesión de usuario** | `sesion:{token}`                 | Hash     | 3600s  | Campos: `user_id`, `rol`, `last_activity`                |
| **Métricas rápidas**  | `stats:reservas:hoy`             | Counter  | 86400s | Incrementado atómicamente en cada reserva confirmada     |

---

## 4. Fases de Implementación

### Fase 1 — `redis_service.py`

Crear `redis_service/redis_service.py` con todas las operaciones encapsuladas. La UI (Streamlit) nunca llama directamente al cliente de Redis.

```python
# redis_service/redis_service.py
import redis
import os

_client = None

def get_client():
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )
    return _client

def ping():
    return get_client().ping()

# --- Disponibilidad ---

def set_disponible(habitacion_id: str, disponible: bool):
    get_client().set(f"habitacion:{habitacion_id}:disponible", "1" if disponible else "0")

def is_disponible(habitacion_id: str) -> bool:
    return get_client().get(f"habitacion:{habitacion_id}:disponible") == "1"

# --- Locks ---

def adquirir_lock(habitacion_id: str, usuario_id: str, ttl: int = 600) -> bool:
    """Retorna True si el lock fue adquirido. Usa NX para atomicidad."""
    return get_client().set(
        f"lock:habitacion:{habitacion_id}", usuario_id, nx=True, ex=ttl
    )

def liberar_lock(habitacion_id: str):
    get_client().delete(f"lock:habitacion:{habitacion_id}")

def get_lock_owner(habitacion_id: str) -> str | None:
    return get_client().get(f"lock:habitacion:{habitacion_id}")

# --- Métricas ---

def incrementar_reservas_hoy():
    client = get_client()
    key = "stats:reservas:hoy"
    client.incr(key)
    client.expire(key, 86400)

def get_reservas_hoy() -> int:
    val = get_client().get("stats:reservas:hoy")
    return int(val) if val else 0

# --- Seeding ---

def seed_from_habitaciones(habitaciones: list):
    """Carga el estado inicial de disponibilidad desde los documentos de Mongo."""
    client = get_client()
    pipe = client.pipeline()
    for h in habitaciones:
        key = f"habitacion:{h['_id']}:disponible"
        value = "1" if h.get("disponible", True) else "0"
        pipe.set(key, value)
    pipe.execute()
```

### Fase 2 — Seeding inicial

Agregar en `admin_tab` de `streamlit_app.py` un botón de mantenimiento que sincronice el estado de Redis con Mongo:

```python
if st.button("Sincronizar disponibilidad → Redis"):
    habitaciones = list(mongo.col_habitaciones.find({}))
    redis_service.seed_from_habitaciones(habitaciones)
    st.success(f"{len(habitaciones)} habitaciones sincronizadas en Redis.")
```

Este paso es necesario porque Redis arranca vacío. Sin él, todas las consultas de disponibilidad devolverán `None`.

### Fase 3 — Flujo de reserva con Redis

Modificar `show_booking_form()` para consultar Redis *antes* de persistir en Mongo.

#### Flujo: Iniciar reserva

```python
habitacion_id = str(habitacion["_id"])
usuario_id = str(usuario["_id"])

if not redis_service.is_disponible(habitacion_id):
    st.error("La habitación no está disponible.")
    return

if not redis_service.adquirir_lock(habitacion_id, usuario_id):
    owner = redis_service.get_lock_owner(habitacion_id)
    st.warning(f"Habitación siendo reservada por otro usuario (lock activo).")
    return

st.session_state["lock_activo"] = habitacion_id
# → Proceder a pantalla de pago / confirmación
```

#### Flujo: Confirmar reserva

```python
habitacion_id = st.session_state.get("lock_activo")

# 1. Validar que el lock sigue siendo nuestro
if redis_service.get_lock_owner(habitacion_id) != usuario_id:
    st.error("El tiempo de reserva expiró. Iniciá el proceso nuevamente.")
    return

# 2. Persistir en MongoDB
save_document(mongo.col_reservas, document)

# 3. Actualizar Redis
redis_service.set_disponible(habitacion_id, False)
redis_service.liberar_lock(habitacion_id)
redis_service.incrementar_reservas_hoy()

# 4. (Futuro) Crear relación en Neo4j — ver sección 6
# 5. (Futuro) Registrar evento en Cassandra
```

### Fase 4 — Panel de estado en Streamlit

Agregar indicadores de conexión en la cabecera o en `admin_tab`:

```python
col_mongo, col_redis = st.columns(2)
col_mongo.metric("MongoDB", "✅ Conectado")
try:
    redis_service.ping()
    col_redis.metric("Redis", "✅ Conectado")
except Exception:
    col_redis.metric("Redis", "❌ No disponible")
```

---

## 5. Relación con Neo4j — Sin Choques

Redis y Neo4j son **ortogonales**: no comparten datos ni se leen entre sí.

| Momento           | Redis                          | Neo4j                              |
| :---------------- | :----------------------------- | :--------------------------------- |
| Iniciar reserva   | Consulta disponibilidad + lock | No interviene                      |
| Confirmar reserva | Actualiza disponible + libera lock | Crea `(Usuario)-[:RESERVO]->(Hotel)` |
| Registrar reseña  | No interviene                  | Crea `(Usuario)-[:CALIFICO]->(Hotel)` |

El único punto de contacto es la **secuencia de confirmación**, donde ambos son actualizados después del save en Mongo.

---

## 6. Manejo de Fallos — Consistencia Eventual

Al confirmar una reserva se actualizan múltiples motores en secuencia. Si uno falla, puede quedar inconsistencia. Para el TPI se aplica la **Opción 1: tolerancia simple**.

```python
# Después de guardar en Mongo y actualizar Redis:
try:
    neo4j_service.crear_relacion_reserva(usuario_id, hotel_id)
except Exception as e:
    print(f"[WARN] Neo4j no disponible, relación no creada: {e}")
    # La reserva en Mongo y el estado en Redis siguen siendo válidos.
    # Limitación documentada: las recomendaciones pueden estar incompletas
    # hasta que Neo4j esté disponible y se re-sincronice.
```

### Opciones de manejo de fallos (por complejidad)

| Opción | Estrategia | Para el TPI |
| :----- | :--------- | :---------- |
| **1** | Log del error, continuar. La reserva es válida. | ✅ Recomendada |
| **2** | Registrar en Cassandra un evento `pendiente_neo4j` para retry posterior | Posible extensión |
| **3** | Revertir todo (Saga Pattern): borrar de Mongo, liberar lock en Redis | Demasiado overhead |

---

## 7. Fallback si Redis no está disponible

Si Redis está caído, el sistema no debe bloquearse. Degradar a consulta directa en Mongo:

```python
def is_disponible_safe(habitacion_id: str, mongo_habitacion: dict) -> bool:
    try:
        return redis_service.is_disponible(habitacion_id)
    except Exception:
        # Fallback: leer campo `disponible` directo de Mongo
        return mongo_habitacion.get("disponible", False)
```

---

## 8. Consideraciones Técnicas

- **Atomicidad**: Usar `NX=True` en el SET del lock para garantizar que solo un proceso lo adquiere. Esto es atómico en Redis.
- **Persistencia**: Configurar Redis con RDB o AOF para no perder el estado de disponibilidad al reiniciar el contenedor.
- **IDs compartidos**: Los `_id` de Mongo se usan como strings en Redis (`str(ObjectId)`). No usar el `ObjectId` directamente.
- **session_state**: El `usuario_id` del lock debe guardarse en `st.session_state` entre reruns de Streamlit, ya que Streamlit no persiste variables locales entre interacciones.
- **TTL del lock**: 600 segundos (10 minutos). Si el usuario abandona el flujo de pago, el lock expira automáticamente y la habitación vuelve a estar disponible.

---

## 9. Orden de Implementación Sugerido

```
[x] 1. redis_service/redis_service.py  ← cliente + funciones atómicas
[ ] 2. Botón de seeding en admin_tab   ← sincronizar Mongo → Redis
[ ] 3. Modificar show_booking_form()   ← consultar Redis antes de guardar
[ ] 4. Flujo de confirmación           ← liberar lock + actualizar disponibilidad
[ ] 5. Panel de estado de conexión     ← mostrar Redis online/offline en la UI
[ ] 6. Integración con Neo4j           ← crear relación tras confirmar reserva
[ ] 7. Integración con Cassandra       ← loguear evento inmutable
```

---

## 10. Test Plan

- [ ] Verificar conexión a Redis desde la app (ping).
- [ ] Ejecutar seeding y confirmar que las keys `habitacion:{id}:disponible` existen en Redis.
- [ ] Intentar reservar una habitación disponible: debe crear lock y luego guardar en Mongo.
- [ ] Intentar reservar la misma habitación con otro usuario mientras el lock está activo: debe ser rechazada.
- [ ] Esperar 600s (o reducir TTL a 5s en tests) y verificar que el lock expira automáticamente.
- [ ] Confirmar reserva: verificar que Redis marca `disponible=0` y elimina el lock.
- [ ] Simular Redis caído: verificar que el fallback a Mongo funciona sin crashear la app.
- [ ] Verificar que `stats:reservas:hoy` se incrementa con cada reserva confirmada.