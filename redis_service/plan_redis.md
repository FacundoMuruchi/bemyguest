## 3. Modelo de Datos (Key-Value Design)

Se usa la convención de `:` como separador de jerarquía. Los IDs son los `_id` de MongoDB serializados como string.

| Caso de Uso           | Key                              | Tipo     | TTL    | Descripción                                              |
| :-------------------- | :------------------------------- | :------- | :----- | :------------------------------------------------------- |
| **Disponibilidad**    | `habitacion:{id}:disponible`     | String   | No     | `"1"` = disponible, `"0"` = no disponible                |
| **Bloqueo temporal**  | `lock:habitacion:{id}`           | String   | 600s   | Valor = `usuario_id`. Evita overbooking durante el pago  |
| **Sesión de usuario** | `sesion:{token}`                 | String   | 3600s  | Valor = `usuario_id`. TTL se renueva en cada lectura     |
| **Métricas rápidas**  | `stats:reservas:hoy`             | Counter  | 86400s | Incrementado atómicamente en cada reserva confirmada     |


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

## 10. Test Plan

- [ ] Verificar conexión a Redis desde la app (ping).
- [ ] Ejecutar seeding y confirmar que las keys `habitacion:{id}:disponible` existen en Redis.
- [ ] Intentar reservar una habitación disponible: debe crear lock y luego guardar en Mongo.
- [ ] Intentar reservar la misma habitación con otro usuario mientras el lock está activo: debe ser rechazada.
- [ ] Esperar 600s (o reducir TTL a 5s en tests) y verificar que el lock expira automáticamente.
- [ ] Confirmar reserva: verificar que Redis marca `disponible=0` y elimina el lock.
- [ ] Simular Redis caído: verificar que el fallback a Mongo funciona sin crashear la app.
- [ ] Verificar que `stats:reservas:hoy` se incrementa con cada reserva confirmada.