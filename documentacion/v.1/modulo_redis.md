# ⚡ Módulo: Integración y Seeding de Redis (`/redis_service`)

Este módulo sienta las bases técnicas y metodológicas para incorporar **Redis** a la plataforma **BeMyGuest**, actuando como el motor complementario a MongoDB encargado de gestionar la **disponibilidad en tiempo real** y evitar problemas de **overbooking** mediante bloqueos atómicos en memoria.

---

## 🏗️ Estructura del Módulo

### 1. `plan_redis.md` (Documentación del Diseño Técnico)
Es el plano arquitectónico integral de la integración. Detalla la justificación y las estructuras de datos de Redis en el ecosistema multi-motor:
* **Estructura de Llaves**: Describe la nomenclatura estructurada y estandarizada utilizando dos puntos (`:`) como separadores lógicos:
  * `habitacion:{id}:disponible` (String): Guarda `"1"` (disponible) o `"0"` (no disponible).
  * `lock:habitacion:{id}` (String con TTL): Bloqueo temporal atómico. Guarda el `usuario_id` que inició el proceso.
  * `sesion:{token}` (Hash): Para guardar estados de sesión activos.
  * `stats:reservas:hoy` (Counter): Contador incremental diario para analítica rápida.
* **Pseudocódigo de Control**: Define los flujos de "Intento de Reserva" y "Confirmación de Reserva", detallando el uso del parámetro `NX=True` (Set if Not Exists) para garantizar la atomicidad en la concurrencia.
* **Consistencia Eventual**: Plantea el análisis de convivencia de Redis con Neo4j para evitar choques transaccionales y describe las alternativas de fallback ante caídas del motor.

---

### 2. `seed_redis.py` (Script de Poblamiento Inicial)
Un script CLI sumamente robusto para poblar el estado de disponibilidad del caché en memoria:
* **Mapeo Inteligente**:
  * Intenta conectarse a MongoDB. Si lo logra, consulta todas las habitaciones registradas, mapea sus IDs de BSON a strings y lee su estado de disponibilidad (`True`/`False`).
  * **Fallback Integrado**: Si MongoDB no está disponible, el script cae automáticamente a un dataset embebido local de 8 habitaciones ficticias estructuradas como ObjectIds para poder realizar pruebas en frío sin dependencias.
* **Escritura Transaccional (`Pipeline`)**:
  * Utiliza un pipeline atómico de Redis (`r.pipeline()`) para enviar todas las llaves en una sola consulta de red. Esto evita el overhead de latencia de red de ida y vuelta.
  * Formatea las llaves de disponibilidad como `habitacion:{id}:disponible`.
* **Mantenimiento Limpio (`--reset`)**:
  * Permite limpiar de forma selectiva únicamente los patrones de llaves del proyecto en Redis (`habitacion:*`, `lock:*`, `sesion:*`, `stats:*`), garantizando no borrar bases de datos de otros proyectos locales (evita el uso peligroso de `FLUSHALL`).
* **Inicialización de Métricas**:
  * Inicializa de manera segura el contador `stats:reservas:hoy` en `"0"` con un TTL de 24 horas (`86400` segundos) en Redis.
