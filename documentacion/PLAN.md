# Conexión Multi-Motor Para BeMyGuest

## Resumen

La plataforma debería mantener **MongoDB como motor principal operacional** para los documentos flexibles actuales: usuarios, hoteles, habitaciones, reservas y reseñas. Los otros motores no deberían reemplazar Mongo, sino complementar casos específicos:

- **Redis** para disponibilidad inmediata y bloqueos temporales.
- **Neo4j** para relaciones y recomendaciones.
- **Cassandra** para logs históricos inmutables y auditoría.

La app de Streamlit puede seguir siendo la interfaz única, pero debería llamar a una capa de servicios que coordine los 4 motores.

## Cambios Clave

- Crear una capa `services/` o similar que oculte la lógica multi-motor:
  - `mongo_service`: alta/consulta de documentos actuales.
  - `redis_service`: disponibilidad, bloqueo y liberación temporal de habitaciones.
  - `neo4j_service`: relaciones usuario-hotel y recomendaciones.
  - `cassandra_service`: registro histórico de eventos.

- Agregar configuración por variables de entorno:
  - `MONGO_URI`
  - `REDIS_HOST`, `REDIS_PORT`
  - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
  - `CASSANDRA_CONTACT_POINTS`, `CASSANDRA_KEYSPACE`

- Mantener los IDs de Mongo como identificadores compartidos:
  - `usuario_id`
  - `hotel_id`
  - `habitacion_id`
  - `reserva_id`
  - En Redis/Neo4j/Cassandra se guardarían como strings para evitar problemas de serialización.

## Flujo Recomendado

- **Registrar usuario**
  - Guardar usuario en Mongo.
  - Crear nodo `Usuario` en Neo4j.
  - Registrar evento `usuario_creado` en Cassandra.

- **Registrar hotel**
  - Guardar hotel en Mongo.
  - Crear nodo `Hotel` en Neo4j.
  - Registrar evento `hotel_creado` en Cassandra.

- **Registrar habitación**
  - Guardar habitación en Mongo.
  - Crear/actualizar clave de disponibilidad en Redis.
  - Relacionar habitación con hotel si se decide modelarla en Neo4j.
  - Registrar evento `habitacion_creada` en Cassandra.

- **Iniciar reserva**
  - Consultar Redis para verificar disponibilidad.
  <!-- - Bloquear habitación con TTL, por ejemplo `lock:habitacion:{habitacion_id}` durante 10 minutos.
  - Si ya existe lock, impedir la reserva. --> Si estamos manejando un único usuario, es necesario esto? o debemos pensarlo para múltiples usuarios?.

- **Confirmar reserva**
  - Validar que el lock sigue vigente.
  - Guardar reserva en Mongo.
  - Marcar disponibilidad en Redis.
  - Crear relación en Neo4j, por ejemplo `(Usuario)-[:RESERVO]->(Hotel)`.
  - Registrar evento inmutable `reserva_confirmada` en Cassandra.

- **Registrar reseña**
  - Guardar reseña en Mongo.
  - Crear relación en Neo4j, por ejemplo `(Usuario)-[:CALIFICO {puntaje}]->(Hotel)`.
  - Registrar evento `reseña_creada` en Cassandra.

## Cambios En Streamlit

- Agregar un panel de estado de conexiones para Mongo, Redis, Neo4j y Cassandra.
- En el formulario de reservas:
  - Mostrar disponibilidad desde Redis.
  - Agregar botón “Bloquear habitación”.
  - Permitir confirmar reserva solo si el bloqueo sigue activo.
- Agregar una pestaña “Recomendaciones”:
  - Seleccionar usuario.
  - Consultar Neo4j.
  - Mostrar hoteles recomendados.
- Agregar una pestaña “Historial”:
  - Consultar Cassandra por `usuario_id`, `habitacion_id` o rango de fechas.

## Test Plan

- Verificar conexión individual a cada motor desde la app.
- Registrar usuario, hotel y habitación, y confirmar que se reflejan en los motores correspondientes.
- Intentar reservar una habitación disponible: debe crear lock en Redis y luego reserva en Mongo.
- Intentar reservar una habitación bloqueada: debe impedir overbooking.
- Confirmar reserva: debe guardar en Mongo, registrar evento en Cassandra y crear relación en Neo4j.
- Consultar recomendaciones con usuario que ya reservó o reseñó hoteles.
- Consultar historial en Cassandra por usuario y por fecha.

## Supuestos

- MongoDB sigue siendo la fuente principal para los documentos completos.
- Redis no almacena historial, solo estado temporal o de disponibilidad.
- Neo4j no duplica todo el documento, solo nodos y relaciones necesarias para recomendaciones.
- Cassandra no se usa para editar datos, solo para eventos inmutables.
- Streamlit sigue siendo una interfaz administrativa/simple, no una app final de producción.
